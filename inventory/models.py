from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import Sum


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
        consumptions = self.lots.all().aggregate(total=models.Sum('consumptions__quantity'))['total'] or 0
        return lots_quantities - consumptions
    
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
        return sum(lot.stock_cost for lot in self.lots.all())
    
    @property
    def lots(self):
        return Lot.objects.filter(purchase_item__product=self).order_by('date_received')

    def is_below_minimum_stock(self):
        return self.stock_level < self.minimum_stock_level
    
    @property
    def average_consumption_past_week(self):
        # Define the time window: now minus 7 days
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)
        
        # Filter SaleItems related to this product and sold in the last 7 days
        total_quantity = (
            SaleItem.objects.filter(product=self, sale__date__gte=one_week_ago, sale__date__lte=now)
            .aggregate(total=models.Sum('quantity'))
        )['total'] or 0
        
        # Divide by 7 to get average daily consumption
        average_daily = total_quantity / 7.0
        return average_daily
    

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

    def __str__(self):
        return f"Purchase {self.id} on {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def total_amount(self):
        return sum(float(item.unit_price)*item.quantity for item in self.items.all())


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.FloatField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.purchase.date.strftime('%Y-%m-%d')} - {self.quantity} x {self.unit_price}"
    
    @property
    def line_total(self):
        return float(self.unit_price)*self.quantity if self.quantity and self.unit_price else 0


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
    def gross_margin(self):
        return self.gross_profit/self.total_amount if self.total_amount else 0


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.FloatField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.sale.date.strftime('%Y-%m-%d')} - {self.quantity} x {self.unit_price}"
    
    @property
    def line_total(self):
        return float(self.unit_price)*self.quantity if self.quantity and self.unit_price else 0


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
            return f"{self.linked_object.product.name} ({self.linked_object.unit_price} x {self.linked_object.quantity})"
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
        return sum(sale.gross_profit for sale in Sale.objects.filter(date__range=[self.open_date, self.close_date]))
    
    @property
    def total_sales(self):
        return sum(sale.total_amount for sale in Sale.objects.filter(date__range=[self.open_date, self.close_date]))
    
    @property
    def total_purchases(self):
        return sum(purchase.total_amount for purchase in Purchase.objects.filter(date__range=[self.open_date, self.close_date]))
    
    @property
    def cost_of_goods_sold(self):
        return sum(sale.cost_of_goods_sold for sale in Sale.objects.filter(date__range=[self.open_date, self.close_date]))
    
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
        Calculate the total value of stock on hand at the start of the reporting period.
        This considers all stock movements that occurred strictly before `open_date`.
        """
        total_value = 0
        products = Product.objects.all()
        for product in products:
            stock_in = product.stock_movements.filter(movement_type='IN', date__lt=self.open_date).aggregate(total=Sum('quantity'))['total'] or 0
            stock_out = product.stock_movements.filter(movement_type='OUT', date__lt=self.open_date).aggregate(total=Sum('quantity'))['total'] or 0
            stock_level_at_open = stock_in - stock_out
            total_value += stock_level_at_open * float(product.purchase_price)
        return total_value
    
    @property
    def closing_stock_value(self):
        """
        Calculate the total value of stock on hand at the end of the reporting period.
        This considers all stock movements that occurred strictly before `close_date`.
        """
        total_value = 0
        products = Product.objects.all()
        for product in products:
            stock_in = product.stock_movements.filter(movement_type='IN', date__lt=self.close_date).aggregate(total=Sum('quantity'))['total'] or 0
            stock_out = product.stock_movements.filter(movement_type='OUT', date__lt=self.close_date).aggregate(total=Sum('quantity'))['total'] or 0
            stock_level_at_close = stock_in - stock_out
            total_value += stock_level_at_close * float(product.purchase_price)
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
    quantity = models.FloatField()
    cost_per_unit = models.DecimalField(max_digits=15, decimal_places=2)
    date_received = models.DateTimeField(default=timezone.now)
    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.purchase_item.product.name} - {self.quantity}"
    
    @property
    def stock_level(self):
        print('self.quantity:', self.quantity)
        print('self.consumptions:', self.consumptions.all())
        return self.quantity - (self.consumptions.aggregate(total=models.Sum('quantity'))['total'] or 0)
    
    @property
    def stock_cost(self):
        return self.stock_level * float(self.cost_per_unit)
    
    @property
    def is_empty(self):
        return self.stock_level == 0
    
    def consume(self, quantity):
        ear_marked = min(quantity, self.stock_level)
        if self.stock_level > 0 and ear_marked > 0:
            LotConsumption.objects.create(lot=self, quantity=ear_marked)
        return quantity - ear_marked
    

class LotConsumption(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='consumptions')
    quantity = models.FloatField()
    date_consumed = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.lot.purchase_item.product.name} - {self.quantity} - {self.date_consumed.strftime('%Y-%m-%d')}"
    
    @property
    def cost(self):
        return self.quantity * self.lot.cost_per_unit
