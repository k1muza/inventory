from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models import DecimalField, Sum, F, ExpressionWrapper


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
        from inventory.models import StockBatch, BatchMovement
        """
        Calculates the total value of all lots' stock on hand 
        as of self.open_date, using each lot's purchase cost.
        """
        total_value = Decimal(0.0)

        for batch in StockBatch.objects.filter(date_received__lt=self.open_date):
            total_in = batch.movements.filter(
                date__lt=self.open_date,
                movement_type=BatchMovement.MovementType.IN,
            ).aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal(0.0)
                )
            )['total']
                
            total_out = batch.movements.filter(
                date__lt=self.open_date,
                movement_type=BatchMovement.MovementType.OUT,
            ).aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal(0.0)
                )
            )['total']

            net_qty = total_in - total_out
            total_value += (net_qty * batch.linked_object.unit_cost)

        return total_value
    
    @property
    def closing_stock_value(self):
        from inventory.models import StockBatch, BatchMovement
        """
        Calculates the total value of all lots' stock on hand 
        as of self.close_date, using each lot's purchase cost.
        """
        total_value = Decimal(0.0)

        for batch in StockBatch.objects.filter(date_received__lt=self.close_date):
            queryset = batch.movements.filter(
                date__lt=self.close_date,
                movement_type=BatchMovement.MovementType.IN,
            )
            total_in = queryset.aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal(0.0)
                )
            )['total']
                
            total_out = batch.movements.filter(
                date__lt=self.close_date,
                movement_type=BatchMovement.MovementType.OUT,
            ).aggregate(
                total=Coalesce(
                    Sum(
                        'quantity',
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal(0.0)
                )
            )['total']

            net_qty = total_in - total_out
            total_value += (net_qty * batch.linked_object.unit_cost)

        return total_value
    
    @property
    def opening_cash(self):
        from inventory.models import Transaction
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
        from inventory.models import Transaction
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
                'stock_level': product.get_stock_level(self.open_date),
                'stock_value': product.get_stock_value(self.open_date),
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
                'stock_level': product.get_stock_level(self.close_date),
                'stock_value': product.get_stock_value(self.close_date),
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
            if product.get_stock_level(self.open_date) or \
                product.get_stock_level(self.close_date) or \
                product.get_outgoing_stock(self.open_date, self.close_date) or \
                product.get_incoming_stock(self.open_date, self.close_date):
                inventory.append({
                    'product': product,
                    'opening_stock_level': product.get_stock_level(self.open_date),
                    'closing_stock_level': product.get_stock_level(self.close_date),
                    'opening_stock_value': product.get_stock_value(self.open_date),
                    'closing_stock_value': product.get_stock_value(self.close_date),
                    'incoming_stock': product.get_incoming_stock(self.open_date, self.close_date),
                    'outgoing_stock': product.get_outgoing_stock(self.open_date, self.close_date),
                    'sales': product.get_total_sales(self.open_date, self.close_date),
                    'cost_of_goods_sold': product.get_cost_of_goods_sold(self.open_date, self.close_date),
                    'gross_profit': product.get_gross_profit(self.open_date, self.close_date),
                })
        return inventory
