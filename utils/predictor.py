from django.db.models import Sum, Q, F, DecimalField, ExpressionWrapper, FloatField, Case, When, Value
from django.db.models.functions import Coalesce
import pandas as pd
from decimal import Decimal
from prophet import Prophet

from inventory.models import SaleItem


class Predictor:
    def get_annotated_saleitems(self, product, start_date, end_date):
        """
        Returns a queryset of SaleItem objects with an extra 'final_quantity' field:
        - final_quantity = quantity if net_stock >= quantity
        - final_quantity = None if net_stock < quantity (stock-limited)
        """
        return (
            SaleItem.objects.filter(
                product=product,
                sale__date__range=[start_date, end_date]
            )
            # 1) Annotate total stock_in (product__stock_movements__quantity where movement_type='IN') up to sale.date
            .annotate(
                stock_in=Coalesce(
                    Sum(
                        'product__stock_movements__quantity',
                        filter=Q(
                            product__stock_movements__movement_type='IN',
                            product__stock_movements__date__lte=F('sale__date')
                        ),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal('0.0')
                ),
                stock_out=Coalesce(
                    Sum(
                        'product__stock_movements__quantity',
                        filter=Q(
                            product__stock_movements__movement_type='OUT',
                            product__stock_movements__date__lte=F('sale__date')
                        ),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal('0.0')
                ),
            )
            # 2) net_stock = stock_in - stock_out
            .annotate(
                net_stock=ExpressionWrapper(
                    F('stock_in') - F('stock_out'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
            # 3) If net_stock < quantity => final_quantity = None, else final_quantity = quantity
            .annotate(
                final_quantity=Case(
                    When(net_stock__lt=F('quantity'), then=Value(None)),  # limited by stock => None
                    default=F('quantity'),  # not limited => keep the original quantity
                    output_field=FloatField()  # or DecimalField
                )
            )
        )

    def build_dataframe_for_prophet(self, product, start_date, end_date):
        """
        Produce a DataFrame where each row corresponds to one SaleItem row.
        'ds' = sale.date, 'y' = final_quantity or 0 if limited by stock.
        """

        qs = self.get_annotated_saleitems(product, start_date, end_date)

        # Extract fields we need (sale.date -> 'ds', final_quantity -> 'y')
        # We'll fill 'y' with 0 in place of None
        records = qs.values(
            'sale__date',   # We'll rename this to 'ds'
            'final_quantity'
        )
        df = pd.DataFrame.from_records(records)

        if not df.empty:
            # Rename the columns for Prophet
            df.rename(columns={'sale__date': 'ds', 'final_quantity': 'y'}, inplace=True)
            
            # Convert ds to datetime
            df['ds'] = pd.to_datetime(df['ds'], errors='coerce')

            # Remove timezone
            df['ds'] = df['ds'].dt.tz_localize(None)

            df['cap'] = 1000.0
            df['floor'] = 0.0

        else:
            # If no items, create an empty frame with the right columns
            df = pd.DataFrame(columns=['ds', 'y'])

        return df
    
    def build_prophet_model(self, df):
        # Create a Prophet instance
        model = Prophet(
            weekly_seasonality=True,  # captures day-of-week effects
            yearly_seasonality=False, # set to True if you suspect yearly patterns
            daily_seasonality=False,  # usually not needed unless you have sub-daily data
            growth='logistic'         # use logistic growth for bounded growth
        )
        
        # Fit the model
        model.fit(df)
        return model
    
    def make_forecast(self, model, days=12):
        # Create a DataFrame with future dates
        future = model.make_future_dataframe(periods=days)
        # lowest bound for y is 0
        future['floor'] = 0.0
        # upper bound for y is infinity
        future['cap'] = 1000.0
        # Make predictions
        forecast = model.predict(future)
        return forecast

    def predict_sales(self, product):
        # Get consumption data for the last 30 days
        end_date = SaleItem.objects.filter(product=product).latest('sale__date').sale.date
        start_date = SaleItem.objects.filter(product=product).earliest('sale__date').sale.date
        df = self.build_dataframe_for_prophet(product, start_date, end_date)
        
        # Prophet expects columns ['ds', 'y']
        # Make sure df has these columns, possibly rename
        df = df.rename(columns={'ds': 'ds', 'y': 'y'})

        # 2. Build and fit the Prophet model
        model = self.build_prophet_model(df)

        # 3. Forecast next 7 days
        forecast = self.make_forecast(model, days=12)

        return forecast.to_dict(orient='records')
