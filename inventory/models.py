from datetime import timedelta
import math
from django.db import models
from django.forms import FloatField
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Q, Count
from django.db.models.functions import Coalesce
from django.conf import settings


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
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
    def lots_stock_level(self):
        """
        Calculate current stock level based on lots.
        """
        lots_quantities = self.lots.all().aggregate(total=models.Sum('quantity'))['total'] or 0
        movements = self.lots.all().aggregate(total=models.Sum('movements__quantity'))['total'] or 0
        return lots_quantities - movements
    
    @property
    def stock_value(self):
        """
        Calculate the total value of stock on hand.
        """
        return self.stock_level * float(self.purchase_price)
    
    @property
    def lots_stock_value(self):
        """
        Calculate the total value of stock on hand based on lots.
        """
        return sum(lot.quantity_remaining_cost for lot in self.lots.all())
    
    @property
    def lots(self):
        return Lot.objects.filter(purchase_item__product=self).order_by('date_received')

    @property
    def average_consumption(self):
        """
        Compute average based on the last N in-stock SaleItems, ignoring items
        that were partially out of stock (net_stock < item.quantity).
        """
        N = settings.AVERAGE_INTERVAL_DAYS  # or a fixed integer like 7
        
        # 1. Start with all SaleItems of this product.
        queryset = SaleItem.objects.filter(product=self)

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
            total_quantity=Coalesce(Sum('quantity'), 0.0),
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
            return self.reorder_quantity * float(purchase_item.unit_cost)
        return 0
        
    @property
    def batch_sized_reorder_value(self):
        purchase_item = self.purchase_items.latest('purchase__date')
        if purchase_item is not None:
            return self.batch_sized_reorder_quantity * float(purchase_item.unit_cost)
        return 0
    
    @property
    def average_gross_profit(self):
        # Define the time window: now minus 7 days
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)

        sales = SaleItem.objects.filter(product=self, sale__date__gte=one_week_ago, sale__date__lte=now)
        total_gross_profit = sum(item.gross_profit for item in sales)
        return total_gross_profit / settings.AVERAGE_INTERVAL_DAYS if total_gross_profit else 0

    @property
    def latest_unit_profit(self):
        saleItem: SaleItem = self.sale_items.latest('sale__date')
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
    
    def is_below_minimum_stock(self):
        return self.stock_level < self.minimum_stock_level
    

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
    ]

    product = models.ForeignKey(Product, related_name='stock_movements', on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity = models.FloatField()
    date = models.DateTimeField(default=timezone.now)
    adjustment = models.BooleanField(default=False)
    
     # GenericForeignKey fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ['content_type', 'object_id']

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.name} - {self.quantity}"


class Purchase(models.Model):
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    is_initial_stock = models.BooleanField(default=False)

    def __str__(self):
        return f"Purchase {self.id} on {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def total_amount(self):
        return sum(float(item.unit_cost)*item.quantity for item in self.items.all())


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchase_items')
    quantity = models.FloatField()
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.purchase.date.strftime('%Y-%m-%d')} - {self.quantity} x {self.unit_cost}"
    
    @property
    def line_total(self):
        return float(self.unit_cost)*self.quantity if self.quantity and self.unit_cost else 0


class Sale(models.Model):
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Sale {self.id} on {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def total_amount(self):
        return sum(float(item.unit_price)*item.quantity for item in self.items.all())
    
    @property
    def cost_of_goods_sold(self):
        return sum(float(item.product.purchase_price)*item.quantity for item in self.items.all())
    
    @property
    def gross_profit(self):
        return self.total_amount - self.cost_of_goods_sold
    
    @property
    def movements(self):
        saleitem_ct = ContentType.objects.get_for_model(SaleItem)
        return LotMovement.objects.filter(
            content_type=saleitem_ct,
            object_id__in=[i['id'] for i in self.items.values('id')]
        )
    
    @property
    def cost(self):
        return (
            self.movements.annotate(
                cost=ExpressionWrapper(
                    F('quantity') * F('lot__purchase_item__unit_cost'),
                    output_field=DecimalField(),
                )
            ).aggregate(total=models.Sum('cost'))['total'] or 0
        )
    
    @property
    def profit(self):
        total_revenue = 0.0
        for movement in self.movements.all():
            # Check if movement.linked_object is a SaleItem
            if movement.linked_object and type(movement.linked_object).__name__ == 'SaleItem':
                sale_item: SaleItem = movement.linked_object
                total_revenue += (movement.quantity * float(sale_item.unit_price))

        return total_revenue - float(self.cost)
    
    @property
    def gross_margin(self):
        return self.gross_profit / self.total_amount if self.total_amount else 0


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sale_items')
    quantity = models.FloatField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.sale.date.strftime('%Y-%m-%d')} - {self.quantity} x {self.unit_price}"
    
    @property
    def line_total(self):
        return float(self.unit_price)*self.quantity if self.quantity and self.unit_price else 0
    
    @property
    def cost_of_goods_sold(self):
        return float(self.product.purchase_price)*self.quantity if self.quantity else 0
    
    @property
    def gross_profit(self):
        return self.line_total - self.cost_of_goods_sold
    
    @property
    def movements(self): 
        saleitem_ct = ContentType.objects.get_for_model(SaleItem)
        return LotMovement.objects.filter(
            object_id=self.pk,
            content_type=saleitem_ct
        )
    
    @property
    def profit(self):
        return 0
    
    @property
    def profit_per_unit(self):
        return 0
    
    @property
    def limited_by_stock(self):
        stock_in = StockMovement.objects.filter(
            product=self.product, 
            movement_type='IN', 
            date__lte=self.sale.date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # Sum all OUT movements up to check_time
        stock_out = StockMovement.objects.filter(
            product=self.product, 
            movement_type='OUT',
            date__lte=self.sale.date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return (stock_in - stock_out) <= self.quantity


class Expense(models.Model):
    date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    category = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.description} - {self.amount}"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase'),
        ('EXPENSE', 'Expense'),
        ('ADJUSTMENT', 'Adjustment'),
    ]

    date = models.DateTimeField(default=timezone.now)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # GenericForeignKey fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ['content_type', 'object_id']
        ordering = ['-date']

    @property
    def item(self):
        if self.linked_object and hasattr(self.linked_object, 'product'):
            if type(self.linked_object) == SaleItem:
                return f"{self.linked_object.product.name} ({self.linked_object.unit_price} x {self.linked_object.quantity})"
            elif type(self.linked_object) == PurchaseItem:
                return f"{self.linked_object.product.name} ({self.linked_object.unit_cost} x {self.linked_object.quantity})"
        elif self.linked_object and hasattr(self.linked_object, 'description'):
            return self.linked_object.description
        return f"{self.transaction_type} - {self.amount}"
    

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
        return sum(sale.total_amount for sale in Sale.objects.filter(date__range=[self.open_date, self.close_date]))
    
    @property
    def total_purchases(self):
        return sum(purchase.total_amount for purchase in Purchase.objects.filter(date__range=[self.open_date, self.close_date]))
    
    @property
    def cost_of_goods_sold(self):
        return self.opening_stock_value + self.total_purchases - self.closing_stock_value
    
    @property
    def total_expenses(self):
        return sum(expense.amount for expense in Expense.objects.filter(date__range=[self.open_date, self.close_date]))
    
    @property
    def net_profit(self):
        return float(self.gross_profit) - float(self.total_expenses)
    
    @property
    def gross_margin(self):
        return self.gross_profit/self.total_sales if self.total_sales else 0
    
    @property
    def net_margin(self):
        return self.net_profit/self.total_sales if self.total_sales else 0
    
    @property
    def sale_items(self):
        return SaleItem.objects.filter(sale__date__range=[self.open_date, self.close_date])
    
    @property
    def opening_stock_value(self):
        """
        Calculates the total value of all lots' stock on hand 
        as of self.open_date, using each lot's purchase cost.
        """
        total_value = 0.0

        for lot in Lot.objects.filter(date_received__lt=self.open_date):
            queryset = lot.movements.filter(
                date__lt=self.open_date,
                movement_type=LotMovement.MovementType.IN,
            )
            total_in = queryset.aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                    ),
                    0.0
                )
            )['total']
                
            total_out = lot.movements.filter(
                date__lt=self.open_date,
                movement_type=LotMovement.MovementType.OUT,
            ).aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                    ),
                    0.0
                )
            )['total']

            net_qty = total_in - total_out
            total_value += (net_qty * float(lot.purchase_item.unit_cost))

        return total_value
    
    @property
    def closing_stock_value(self):
        """
        Calculates the total value of all lots' stock on hand 
        as of self.close_date, using each lot's purchase cost.
        """
        total_value = 0.0

        for lot in Lot.objects.filter(date_received__lt=self.close_date):
            queryset = lot.movements.filter(
                date__lt=self.close_date,
                movement_type=LotMovement.MovementType.IN,
            )
            total_in = queryset.aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                    ),
                    0.0
                )
            )['total']
                
            total_out = lot.movements.filter(
                date__lt=self.close_date,
                movement_type=LotMovement.MovementType.OUT,
            ).aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                    ),
                    0.0
                )
            )['total']

            net_qty = total_in - total_out
            total_value += (net_qty * float(lot.purchase_item.unit_cost))

        return total_value
    
    @property
    def opening_cash(self):
        """
        Calculate the total cash available at the start of the reporting period.
        This considers all transactions that occurred strictly before `open_date`.
        """
        total_cash = 0
        transactions = Transaction.objects.filter(date__lt=self.open_date)
        for transaction in transactions:
            if transaction.transaction_type == 'SALE':
                total_cash += transaction.amount
            elif transaction.transaction_type == 'PURCHASE':
                total_cash -= transaction.amount
            elif transaction.transaction_type == 'EXPENSE':
                total_cash -= transaction.amount
            elif transaction.transaction_type == 'ADJUSTMENT':
                total_cash += transaction.amount
        return total_cash

    @property
    def closing_cash(self):
        """
        Calculate the total cash available at the end of the reporting period.
        This considers all transactions that occurred strictly before `close_date`.
        """
        total_cash = 0
        transactions = Transaction.objects.filter(date__lt=self.close_date)
        for transaction in transactions:
            if transaction.transaction_type == 'SALE':
                total_cash += transaction.amount
            elif transaction.transaction_type == 'PURCHASE':
                total_cash -= transaction.amount
            elif transaction.transaction_type == 'EXPENSE':
                total_cash -= transaction.amount
            elif transaction.transaction_type == 'ADJUSTMENT':
                total_cash += transaction.amount
        return total_cash


class Lot(models.Model):
    purchase_item = models.OneToOneField(PurchaseItem, on_delete=models.CASCADE)
    date_received = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['date_received', 'id']

    def __str__(self):
        return f"{self.date_received.date()} - {self.purchase_item.product.name} - {self.purchase_item.quantity} {self.purchase_item.product.unit}"
    
    @property
    def quantity_remaining(self):
        return self.purchase_item.quantity - (
            self.movements.filter(
                movement_type=LotMovement.MovementType.OUT,
            ).aggregate(total=models.Sum('quantity'))['total'] or 0)
    
    @property
    def quantity_remaining_cost(self):
        return self.quantity_remaining * float(self.purchase_item.unit_cost)
    
    @property
    def is_empty(self):
        return self.quantity_remaining <= 0
    
    @property
    def profit(self):
        """
        Calculate profit using database-level aggregation:
        profit = sum(quantity * (selling_price - unit_cost)) for all movements
        This is equivalent to:
        profit = sum(quantity * selling_price) - unit_cost * sum(quantity)
        """
        # return (
        #     self.movements.annotate(
        #         profit=ExpressionWrapper(
        #             F('quantity') * (F('sale_item__unit_price') - F('lot__purchase_item__unit_cost')),
        #             output_field=DecimalField(),
        #         )
        #     ).aggregate(total=models.Sum('profit'))['total'] or 0
        # )
        return 0
    
    def consume(self, quantity, sale_item: SaleItem=None):
        ear_marked = min(quantity, self.quantity_remaining)
        sale_ct = ContentType.objects.get_for_model(SaleItem)
        
        if self.quantity_remaining > 0 and ear_marked > 0:
            self.movements.create(
                lot=self, 
                content_type=sale_ct,
                object_id=sale_item.id if sale_item else None,
                quantity=ear_marked, 
                date=sale_item.sale.date if sale_item else timezone.now(),
                movement_type=LotMovement.MovementType.OUT,
            )
        return quantity - ear_marked


class LotMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'
        ADJUSTMENT = 'ADJ', 'Adjustment'
        
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=10, choices=MovementType.choices)
    quantity = models.FloatField()
    date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255, blank=True, null=True)

    # GenericForeignKey fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')
    
    def __str__(self):
        return f"{self.lot.purchase_item.product.name} - {self.quantity} - {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def cost(self):
        return self.quantity * float(self.lot.purchase_item.unit_cost)
    
    @property
    def revenue(self):
        if self.sale_item:
            return self.quantity * float(self.sale_item.unit_price)
        return 0
    
    @property
    def profit(self):
        return self.revenue - self.cost


class Cutting(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE)
    starting_weight = models.DecimalField(max_digits=10, decimal_places=3)
    ending_weight = models.DecimalField(max_digits=10, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.date.date()} {self.lot.purchase_item.product.name}"

    @property
    def total_cost(self):
        return self.starting_weight * self.unit_cost

    @property
    def weight_reduction(self):
        return self.starting_weight - self.ending_weight


class MeatProcess(models.Model):
    class ProcessType(models.TextChoices):
        CUTTING = 'CUT', 'Cut'
        SLICING = 'SLICE', 'Slice'
        MINCING = 'MINCE', 'Mince'
        PACKAGING = 'PACKAGE', 'Package'

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE)
    process_type = models.CharField(max_length=20, choices=ProcessType.choices)
    starting_weight = models.DecimalField(max_digits=10, decimal_places=3)
    ending_weight = models.DecimalField(max_digits=10, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.date.date()} {self.get_process_type_display()} {self.lot.purchase_item.product.name}"

    @property
    def total_cost(self):
        return self.starting_weight * self.unit_cost

    @property
    def weight_reduction(self):
        return self.starting_weight - self.ending_weight
