from datetime import timedelta
from decimal import Decimal
import math
import uuid
from django.db import models
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Q, Count, Case, When, Value, QuerySet
from django.db.models.functions import Coalesce
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    minimum_stock_level = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=20, blank=True)
    batch_size = models.PositiveIntegerField(default=1)
    predict_demand = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        Calculate current stock level based on batches.
        """
        from inventory.models.stock_batch import StockBatchQuerySet
        qs: StockBatchQuerySet = self.batches

        return (
            qs.filter(date_received__lt=timezone.now())
            .annotate_remaining_quantities()
            .filter_empty_batches()
            .aggregate(total=Sum('outstanding'))['total'] or 0
        )

    @property
    def stock_value(self):
        """
        Calculate the product's stock value using DB-level aggregation.
        For each batch received before `date`, this computes:
            (net quantity = total_in - total_out) * effective_unit_cost
        where the effective_unit_cost is determined based on the linked object type:
        - PurchaseItem, StockAdjustment, or StockConversion.
        Only batches with a positive net quantity are included.
        """
        return self.get_stock_value_at()

    @cached_property
    def batches(self) -> QuerySet:
        from inventory.models import StockAdjustment, StockConversion, PurchaseItem, StockBatch

        return StockBatch.objects.filter(
            Q(
                content_type=ContentType.objects.get_for_model(PurchaseItem),
                object_id__in=self.purchase_items.values_list('id', flat=True)
            )
            | Q(
                content_type=ContentType.objects.get_for_model(StockAdjustment),
                object_id__in=self.adjustments.values_list('id', flat=True)
            )
            | Q(
                content_type=ContentType.objects.get_for_model(StockConversion),
                object_id__in=self.conversions_to.values_list('id', flat=True)
            )
        ).order_by('date_received')

    @property
    def average_consumption(self):
        """
        Compute average based on the last N in-stock SaleItems, ignoring items
        that were partially out of stock (net_stock < item.quantity).
        """
        N = settings.AVERAGE_INTERVAL_DAYS

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

    def get_stock_level_at(self, date):
        """
        Calculate stock level at a specific date.
        """
        stock_in = self.stock_movements.filter(movement_type='IN', date__lt=date).aggregate(total=models.Sum('quantity'))['total'] or 0
        stock_out = self.stock_movements.filter(movement_type='OUT', date__lt=date).aggregate(total=models.Sum('quantity'))['total'] or 0
        return stock_in - stock_out

    def get_incoming_stock_between(self, start_date, end_date):
        """
        Calculate stock increase between two dates.
        """
        stock_in = self.stock_movements.filter(movement_type='IN', date__gte=start_date, date__lt=end_date).aggregate(total=models.Sum('quantity'))['total'] or 0
        return stock_in

    def get_outgoing_stock_between(self, start_date, end_date):
        """
        Calculate stock decrease between two dates.
        """
        stock_out = self.stock_movements.filter(movement_type='OUT', date__gte=start_date, date__lt=end_date).aggregate(total=models.Sum('quantity'))['total'] or 0
        return stock_out

    def get_stock_value_at(self, date=timezone.now()):
        """
        Calculate stock value at a specific date.
        """
        from inventory.models.stock_batch import StockBatchQuerySet
        from inventory.models.batch_movement import BatchMovement
        qs: StockBatchQuerySet = self.batches
        qs = qs.filter(date_received__lt=date)
        qs = qs.annotate(
            outstanding=Coalesce(
                Sum(
                    Case(
                        When(
                            movements__movement_type=BatchMovement.MovementType.IN,
                            movements__date__lt=date,
                            then=F('movements__quantity')),
                        When(
                            movements__movement_type=BatchMovement.MovementType.OUT,
                            movements__date__lt=date,
                            then=-F('movements__quantity')),
                        default=Value(Decimal('0.0')),
                    )
                ),
                Value(Decimal('0.0')),
            ),
        )
        qs = qs.filter_empty_batches()
        qs = qs.annotate_unit_costs()
        qs = qs.annotate_remaining_values()
        qs = qs.aggregate(total_value=Coalesce(Sum('batch_value'), Value(Decimal('0.0'))))

        return qs['total_value'] or 0

    def is_below_minimum_stock(self):
        return self.stock_level < self.minimum_stock_level

    def consume(self, quantity, obj):
        """
        Consume stock from the oldest batch(s) available.
        """
        from inventory.models import StockBatch
        remaining = quantity
        while remaining > 0:
            try:
                batch: StockBatch = self.batches.annotate_remaining_quantities().filter(outstanding__gt=0.0001).earliest('date_received')
            except StockBatch.DoesNotExist as e:
                raise ValueError(f"Insufficient stock for {quantity} {self.unit} of {self.name} on {obj}")

            remaining = batch.consume(remaining, obj)

        if remaining > 0.001:
            raise ValueError(f"Insufficient stock for {quantity} {self.unit} of {self.name} on {obj}")

    def get_total_purchases_between(self, start_date, end_date):
        """
        Get all purchase items between two dates.
        """
        return self.purchase_items.filter(
            purchase__date__range=[start_date, end_date]
        ).annotate(
            line_total=ExpressionWrapper(
                F('quantity') * F('unit_cost'),
                output_field=DecimalField(max_digits=10, decimal_places=3)
            )
        ).aggregate(total=models.Sum('line_total'))['total'] or 0

    def get_gross_profit_between(self, start_date, end_date):
        """
        Calculate gross profit
        Sales - Cost of goods sold (opening stock value + purchases - closing stock value)
        """
        sales = self.get_total_sales_between(start_date, end_date)
        conversions_from = self.get_conversions_from_value_between(start_date, end_date)
        cost_of_goods_sold = self.get_cost_of_goods_sold_between(start_date, end_date)

        return sales + conversions_from - cost_of_goods_sold

    def get_total_sales_between(self, start_date, end_date):
        """
        Get all sale items between two dates.
        """
        return self.sale_items.filter(
            sale__date__range=[start_date, end_date]
        ).annotate(
            line_total=ExpressionWrapper(
                F('quantity') * F('unit_price'),
                output_field=DecimalField(max_digits=10, decimal_places=3)
            )
        ).aggregate(total=models.Sum('line_total'))['total'] or 0

    def get_cost_of_goods_sold_between(self, start_date, end_date):
        """
        Get cost of goods sold between two dates
        """
        opening_stock_value = self.get_stock_value_at(start_date)
        closing_stock_value = self.get_stock_value_at(end_date)
        purchases = self.get_total_purchases_between(start_date, end_date)
        conversions_to = self.get_conversions_to_value_between(start_date, end_date)

        return (
            opening_stock_value
            + conversions_to
            + purchases
            - closing_stock_value
        )

    def get_conversions_from_quantity_between(self, start_date, end_date):
        """
        Get all stock conversions in between two dates.
        """
        return self.conversions_from.filter(
            date__range=[start_date, end_date],
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_conversions_to_quantity_between(self, start_date, end_date):
        """
        Get all stock conversions in between two dates.
        """
        return self.conversions_to.filter(
            date__range=[start_date, end_date],
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_conversions_to_value_between(self, start_date, end_date):
        """
        Get all stock conversions in between two dates.
        """
        return self.conversions_to.filter(
            date__range=[start_date, end_date],
        ).annotate(
            line_total=ExpressionWrapper(
                F('quantity') * F('unit_cost'),
                output_field=DecimalField(max_digits=10, decimal_places=3)
            )
        ).aggregate(total=models.Sum('line_total'))['total'] or 0

    def get_conversions_from_value_between(self, start_date, end_date):
        """
        Get all stock conversions in between two dates.
        """
        return self.conversions_from.filter(
            date__range=[start_date, end_date],
        ).annotate(
            line_total=ExpressionWrapper(
                F('quantity') * F('unit_cost'),
                output_field=DecimalField(max_digits=10, decimal_places=3)
            )
        ).aggregate(total=models.Sum('line_total'))['total'] or 0

    def get_average_unit_cost_between(self, start_date, end_date):
        """
        Get average cost between two dates.
        """
        total_cost = self.get_total_purchases_between(start_date, end_date)
        total_weight = self.purchase_items.filter(
            purchase__date__range=[start_date, end_date],
            product=self,
        ).aggregate(
            total_weight=models.Sum('quantity')
        )['total_weight'] or 0

        if total_weight == 0:
            return 0

        return total_cost / total_weight

    def get_average_unit_price_between(self, start_date, end_date):
        """
        Calculate the average unit price of sales for this product between two dates.

        Args:
            start_date: The start date of the period to calculate the average unit price.
            end_date: The end date of the period to calculate the average unit price.

        Returns:
            The average unit price as a decimal value, or 0 if no sales were found in the given period.
        """

        from inventory.models import SaleItem

        return SaleItem.objects.filter(
            sale__date__range=[start_date, end_date],
            product=self,
        ).aggregate(
            average_cost=models.Avg('unit_price')
        )['average_cost'] or 0

    def get_adjustments_between(self, start_date, end_date):
        return self.adjustments.filter(
            date__range=[start_date, end_date]
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_average_unit_cost_with_adjustments_between(self, start_date, end_date):
        from inventory.models import PurchaseItem

        total_weight = PurchaseItem.objects.filter(
            purchase__date__range=[start_date, end_date],
            product=self,
        ).aggregate(
            total_weight=models.Sum('quantity')
        )['total_weight'] or 0

        total_cost = self.get_total_purchases_between(start_date, end_date)

        adjusted_weight = self.get_adjustments_between(start_date, end_date)

        if (total_weight + adjusted_weight) == 0:
            return 0

        return total_cost / (total_weight + adjusted_weight)

    def get_average_unit_profit_between(self, start_date, end_date):
        return (
            self.get_average_unit_price_between(start_date, end_date)
            - self.get_average_unit_cost_with_adjustments_between(start_date, end_date)
        )

    def get_sold_quantity_between(self, start_date, end_date):
        return self.sale_items.filter(
            sale__date__range=[start_date, end_date]
        ).aggregate(total=models.Sum('quantity'))['total'] or 0
