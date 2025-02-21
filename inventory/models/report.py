from decimal import Decimal
from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models import DecimalField, Sum, F, ExpressionWrapper, Case, When, Value, Q, Sum, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.contrib.contenttypes.models import ContentType


class Report(models.Model):
    open_date = models.DateTimeField(default=timezone.now)
    close_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.open_date.strftime('%Y-%m-%d') + ' - ' + self.close_date.strftime('%Y-%m-%d')
    
    @property
    def gross_profit(self):
        return self.total_sales - self.cost_of_goods_sold
    
    @property
    def total_sales(self):
        from inventory.models import SaleItem
        return SaleItem.objects.filter(sale__date__range=[self.open_date, self.close_date]).annotate(
            line_total=ExpressionWrapper(
                F('quantity') * F('unit_price'),
                output_field=DecimalField(max_digits=10, decimal_places=3)
            )
        ).aggregate(total=models.Sum('line_total'))['total'] or 0


    
    @property
    def total_purchases(self):
        from inventory.models import PurchaseItem
        return PurchaseItem.objects.filter(purchase__date__range=[self.open_date, self.close_date]).annotate(
            line_total=ExpressionWrapper(
                F('quantity') * F('unit_cost'),
                output_field=DecimalField(max_digits=10, decimal_places=3)
            )
        ).aggregate(total=models.Sum('line_total'))['total'] or 0
    
    @property
    def cost_of_goods_sold(self):
        return self.opening_stock_value + self.total_purchases - self.closing_stock_value
    
    
    @property
    def total_expenses(self):
        from inventory.models import Expense
        return Expense.objects.filter(date__range=[self.open_date, self.close_date]).aggregate(
            total=Sum('amount')
        )['total']
    
    @property
    def net_profit(self):
        return self.gross_profit - self.total_expenses
    
    @property
    def gross_margin(self):
        return self.gross_profit/self.total_sales if self.total_sales else 0
    
    @property
    def net_margin(self):
        return self.net_profit/self.total_sales if self.total_sales else 0
    
    @property
    def sale_items(self):
        from inventory.models import SaleItem
        return SaleItem.objects.filter(sale__date__range=[self.open_date, self.close_date])
    
    @property
    def opening_stock_value(self):
        return self.get_stock_value_at(self.open_date)
    
    @property
    def closing_stock_value(self):
        return self.get_stock_value_at(self.close_date)
    
    @property
    def opening_cash(self):
        return self.get_cash_at(self.open_date)

    @property
    def closing_cash(self):
        return self.get_cash_at(self.close_date)
    
    @property
    def expenses(self):
        """
        Return a list of dicts, each containing:
            - description
            - amount
            - category

        This implementation pushes the grouping and summing of expenses into the database.
        """
        from inventory.models import Expense
        qs = Expense.objects.filter(date__range=[self.open_date, self.close_date])
        # Group by description and category, and sum the amount for each group.
        return qs.values('description', 'category').annotate(amount=Sum('amount')).values('description', 'amount').order_by('-amount')
    
    @property
    def opening_inventory(self):
        """
        Return a list of dicts, each containing:
            - product name
            - stock level
            - stock value
        based on the current state of the inventory at the time of close_date 
        (or open_date, depending on your needs).
        """
        from inventory.models import Product
        inventory = []
        for product in Product.objects.all():
            inventory.append({
                'product': product.name,
                'stock_level': product.get_stock_level_at(self.open_date),
                'stock_value': product.get_stock_value_at(self.open_date),
            })
        return inventory
    
    @property
    def closing_inventory(self):
        """
        Return a list of dicts, each containing:
            - product name
            - stock level
            - stock value
        based on the current state of the inventory at the time of close_date 
        (or open_date, depending on your needs).
        """
        from inventory.models import Product
        inventory = []
        for product in Product.objects.all():
            inventory.append({
                'product': product.name,
                'stock_level': product.get_stock_level_at(self.close_date),
                'stock_value': product.get_stock_value_at(self.close_date),
            })
        return inventory
    
    # TODO: Resolve how conversions affect the profitability report
    @property
    def inventory_balances(self):
        """
        Return a list of dicts, each containing:
            - product name
            - opening stock level
            - closing stock level
            - opening stock value
            - closing stock value
        """
        from inventory.models import Product
        inventory = []
        for product in Product.objects.all():
            if product.get_stock_level_at(self.open_date) or \
                product.get_stock_level_at(self.close_date) or \
                product.get_outgoing_stock_between(self.open_date, self.close_date) or \
                product.get_incoming_stock_between(self.open_date, self.close_date):
                inventory.append({
                    'product': product,
                    'opening_stock_level': product.get_stock_level_at(self.open_date),
                    'closing_stock_level': product.get_stock_level_at(self.close_date),
                    'opening_stock_value': product.get_stock_value_at(self.open_date),
                    'closing_stock_value': product.get_stock_value_at(self.close_date),
                    'adjustments': product.get_adjustments_between(self.open_date, self.close_date),
                    'incoming_stock': product.get_incoming_stock_between(self.open_date, self.close_date),
                    'conversions_from': product.get_conversions_from_quantity_between(self.open_date, self.close_date),
                    'conversions_to': product.get_conversions_to_quantity_between(self.open_date, self.close_date),
                    'outgoing_stock': product.get_outgoing_stock_between(self.open_date, self.close_date),
                    'sold_stock': product.get_sold_quantity_between(self.open_date, self.close_date),
                })
        return inventory
    

    @property
    def product_performances(self):
        from inventory.models import Product
        perfomances = []
        for product in Product.objects.all():
            if product.get_stock_level_at(self.open_date) or \
                product.get_stock_level_at(self.close_date) or \
                product.get_outgoing_stock_between(self.open_date, self.close_date) or \
                product.get_incoming_stock_between(self.open_date, self.close_date):
                perfomances.append({
                    'product': product,
                    'sales': product.get_total_sales_between(self.open_date, self.close_date),
                    'opening_stock_value': product.get_stock_value_at(self.open_date),
                    'purchases': product.get_total_purchases_between(self.open_date, self.close_date),
                    'closing_stock_value': product.get_stock_value_at(self.close_date),
                    'cost_of_goods_sold': product.get_cost_of_goods_sold_between(self.open_date, self.close_date),
                    'gross_profit': product.get_gross_profit_between(self.open_date, self.close_date),
                    'conversions_from': product.get_conversions_from_value_between(self.open_date, self.close_date),
                    'conversions_to': product.get_conversions_to_value_between(self.open_date, self.close_date),
                    'average_unit_cost_with_adjustments': product.get_average_unit_cost_with_adjustments_between(self.open_date, self.close_date),
                    'average_unit_cost': product.get_average_unit_cost_between(self.open_date, self.close_date),
                    'adjustments': product.get_adjustments_between(self.open_date, self.close_date),
                    'average_unit_price': product.get_average_unit_price_between(self.open_date, self.close_date),
                    'average_unit_profit': product.get_average_unit_profit_between(self.open_date, self.close_date),
                })
        return perfomances

    def get_stock_value_at(self, date):
        from inventory.models import StockBatch, BatchMovement, PurchaseItem, StockAdjustment, StockConversion  
        return StockBatch.objects.filter(date_received__lt=date).annotate(
            total_in=Coalesce(
                Sum(
                    'movements__quantity',
                    filter=Q(movements__date__lt=date, movements__movement_type=BatchMovement.MovementType.IN),
                ),
                Value(Decimal(0.0))
            ),
            total_out=Coalesce(
                Sum(
                    'movements__quantity',
                    filter=Q(movements__date__lt=date, movements__movement_type=BatchMovement.MovementType.OUT),
                ),
                Value(Decimal(0.0))
            ),
            net_qty=F('total_in') - F('total_out')
        ).annotate(
            value=ExpressionWrapper(
                F('net_qty') * Case(
                    When(content_type=ContentType.objects.get_for_model(PurchaseItem),
                        then=Subquery(
                            PurchaseItem.objects.filter(pk=OuterRef('object_id')).values('unit_cost')[:1]
                        )),
                    When(content_type=ContentType.objects.get_for_model(StockAdjustment),
                        then=Subquery(
                            StockAdjustment.objects.filter(pk=OuterRef('object_id')).values('unit_cost')[:1]
                        )),
                    When(content_type=ContentType.objects.get_for_model(StockConversion),
                        then=Subquery(
                            StockConversion.objects.filter(pk=OuterRef('object_id')).values('unit_cost')[:1]
                        )),
                    default=Value(Decimal(0.0)),
                ),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        ).aggregate(total=Coalesce(Sum('value'), Value(Decimal(0.0))))['total']

    def get_cash_at(self, date):
        from inventory.models import Transaction
        return Transaction.objects.filter(date__lt=date).aggregate(
            total_cash=Sum(
                Case(
                    When(transaction_type='SALE', then=F('amount')),
                    When(transaction_type='PURCHASE', then=-F('amount')),
                    When(transaction_type='EXPENSE', then=-F('amount')),
                    When(transaction_type='ADJUSTMENT', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
        )['total_cash'] or 0
