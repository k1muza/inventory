from datetime import timedelta
from decimal import Decimal
import math
from django.db import models
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Q, Count
from django.db.models.functions import Coalesce
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property

from inventory.models.stock_batch import StockBatch


class Product(models.Model):
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_stock_level = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=20, blank=True)
    batch_size = models.PositiveIntegerField(default=1)
    predict_demand = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

    @property
    def stock_level(self):
        """
        Calculate current stock level based on stock movements.
        """
        stock_in = self.stock_movements.filter(movement_type='IN').aggregate(total=models.Sum('quantity'))['total'] or 0
        stock_out = self.stock_movements.filter(movement_type='OUT').aggregate(total=models.Sum('quantity'))['total'] or 0
        return stock_in - stock_out
    
    @property
    def batch_based_stock_level(self):
        """
        Calculate batch level based on stock batches.
        """
        return sum(batch.quantity_remaining for batch in self.batches)
    
    @property
    def stock_value(self):
        """
        Sum up quantity_remaining * the batch's unit_cost 
        across all *non-empty* or relevant batches.
        """
        from decimal import Decimal
        total_value = Decimal('0.0')

        for batch in self.batches:
            if not batch.is_empty:
                qty = batch.quantity_remaining
                cost = batch.unit_cost
                total_value += (qty * cost)

        return total_value
    
    @cached_property
    def batches(self):
        from inventory.models import StockAdjustment, StockConversion, PurchaseItem, StockBatch

        return StockBatch.objects.filter(
            Q(
                content_type=ContentType.objects.get_for_model(PurchaseItem),
                object_id__in=self.purchase_items.values_list('id', flat=True)
            ) |
            Q(
                content_type=ContentType.objects.get_for_model(StockAdjustment),
                object_id__in=self.adjustments.values_list('id', flat=True)
            ) |
            Q(
                content_type=ContentType.objects.get_for_model(StockConversion),
                object_id__in=self.conversions.values_list('id', flat=True)
            )
        ).order_by('date_received')

    @property
    def average_consumption(self):
        """
        Compute average based on the last N in-stock SaleItems, ignoring items
        that were partially out of stock (net_stock < item.quantity).
        """
        N = settings.AVERAGE_INTERVAL_DAYS  # or a fixed integer like 7
        
        # 1. Start with all SaleItems of this product.
        queryset = self.sale_items.all()

        # 2. Annotate how much stock was available at sale time.
        #    This is the same logic as before to figure out in-stock vs out-of-stock.
        annotated_items = queryset.annotate(
            stock_in=Coalesce(
                Sum(
                    'product__stock_movements__quantity',
                    filter=Q(
                        product__stock_movements__movement_type='IN',
                        product__stock_movements__date__lt=F('sale__date')
                    )
                ), 
                0
            ),
            stock_out=Coalesce(
                Sum(
                    'product__stock_movements__quantity',
                    filter=Q(
                        product__stock_movements__movement_type='OUT',
                        product__stock_movements__date__lt=F('sale__date')
                    )
                ), 
                0
            ),
        ).annotate(
            net_stock=ExpressionWrapper(
                F('stock_in') - F('stock_out'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )

        # 3. Filter to keep only items that were fully in stock at the time of sale.
        #    net_stock > quantity => not limited by stock.
        in_stock_items = (
            annotated_items
            .filter(net_stock__gte=F('quantity'))
            .order_by('-sale__date')  # most recent items first
        )

        # 4. Limit to the last N items
        last_n_items = in_stock_items[:N]

        # 5. Aggregate total quantity and count.
        aggs = last_n_items.aggregate(
            total_quantity=Coalesce(Sum('quantity'), Decimal('0.0')),
            total_count=Coalesce(Count('id'), 0)
        )
        total_quantity = aggs['total_quantity']
        total_count = aggs['total_count']

        if total_count > 0:
            average = total_quantity / total_count
        else:
            average = 0
        
        return average
    
    @property
    def days_until_stockout(self):
        if self.average_consumption:
            return self.stock_level / self.average_consumption
        return 0
    
    @property
    def reorder_quantity(self):
        interval = settings.REORDER_INTERVAL_DAYS

        avg_daily = self.average_consumption
        if avg_daily <= 0:
            # No consumption means no purchase needed to last 7 days (you already have infinite or no sales)
            return 0
        current_days = self.days_until_stockout
        if current_days >= interval:
            return 0  # Already have enough stock
        # Calculate how much is needed to get to 7 days
        required = (interval * avg_daily) - self.stock_level
        return required if required > 0 else 0
    
    @property
    def batch_sized_reorder_quantity(self):
        batches = self.reorder_quantity / self.batch_size
        return math.ceil(batches) * self.batch_size
    
    @property
    def reorder_value(self):
        purchase_item = self.purchase_items.latest('purchase__date')
        if purchase_item is not None:
            return self.reorder_quantity * purchase_item.unit_cost
        return 0
        
    @property
    def batch_sized_reorder_value(self):
        purchase_item = self.purchase_items.latest('purchase__date')
        if purchase_item is not None:
            return self.batch_sized_reorder_quantity * purchase_item.unit_cost
        return 0
    
    @property
    def average_unit_cost(self):
        """
        Returns average unit cost across non-empty batches, or 0 if none.
        """
        qs = self.batches
        total_quantity, total_cost = (Decimal('0.0'), Decimal('0.0'))
        for b in qs:
            remaining_qty = b.quantity_remaining
            total_quantity += remaining_qty
            total_cost += (remaining_qty * b.linked_object.unit_cost)

        return total_cost / total_quantity if total_quantity > 0 else Decimal('0.0')


    @property
    def average_gross_profit(self):
        # Define the time window: now minus 7 days
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)

        sales = self.sale_items.filter(sale__date__gte=one_week_ago, sale__date__lte=now)
        total_gross_profit = sum(item.gross_profit for item in sales)
        return total_gross_profit / settings.AVERAGE_INTERVAL_DAYS if total_gross_profit else 0

    @property
    def latest_unit_profit(self):
        saleItem = self.sale_items.latest('sale__date')
        if saleItem:
            return saleItem.profit_per_unit
        return 0
    
    def get_stock_level(self, date):
        """
        Calculate stock level at a specific date.
        """
        stock_in = self.stock_movements.filter(movement_type='IN', date__lte=date).aggregate(total=models.Sum('quantity'))['total'] or 0
        stock_out = self.stock_movements.filter(movement_type='OUT', date__lte=date).aggregate(total=models.Sum('quantity'))['total'] or 0
        return stock_in - stock_out
    
    def get_incoming_stock(self, start_date, end_date):
        """
        Calculate stock increase between two dates.
        """
        stock_in = self.stock_movements.filter(movement_type='IN', date__gt=start_date, date__lte=end_date).aggregate(total=models.Sum('quantity'))['total'] or 0
        return stock_in
    
    def get_outgoing_stock(self, start_date, end_date):
        """
        Calculate stock decrease between two dates.
        """
        stock_out = self.stock_movements.filter(movement_type='OUT', date__gt=start_date, date__lte=end_date).aggregate(total=models.Sum('quantity'))['total'] or 0
        return stock_out
    
    def get_stock_value(self, date):
        """
        Calculate stock value at a specific date.
        """
        total_value = Decimal('0.0')

        for batch in self.batches:
            if batch.date_received <= date:
                qty = batch.get_quantity_remaining(date)
                cost = batch.unit_cost
                total_value += (qty * cost)

        return total_value
    
    def is_below_minimum_stock(self):
        return self.stock_level < self.minimum_stock_level
    
    def consume(self, quantity, sale_item):
        """
        Consume stock from the oldest batch(s) available.
        """
        remaining = quantity
        for batch in self.batches.order_by('date_received'):
            if batch.is_empty:
                continue

            remaining = batch.consume(remaining, sale_item)
            
            if remaining <= 0:
                break

        if remaining > 0.001:
            raise ValueError(f"Insufficient stock for {quantity} {self.unit} of {self.name} on {sale_item.sale.date}")
    
