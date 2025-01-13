from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.db.models import F, ExpressionWrapper, DecimalField, Subquery, OuterRef, Value, Case, When


class SaleItem(models.Model):
    sale = models.ForeignKey('inventory.Sale', related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE, related_name='sale_items')
    quantity = models.DecimalField(decimal_places=3, max_digits=15)
    unit_price = models.DecimalField(max_digits=15, decimal_places=6)

    movements = GenericRelation('inventory.BatchMovement', related_query_name='sale_item')
    transactions = GenericRelation('inventory.Transaction', related_query_name='sale_item')

    def __str__(self):
        return f"{self.product.name} - {self.sale.date.strftime('%Y-%m-%d')} - {self.quantity} x {self.unit_price}"
    
    @property
    def date(self):
        return self.sale.date
    
    @property
    def line_total(self):
        return Decimal(self.unit_price)*self.quantity if self.quantity and self.unit_price else 0
    
    @property
    def cost(self):
        from inventory.models import PurchaseItem, StockAdjustment, StockConversion
        movements_with_cost = self.movements.annotate(
            cost_price=Case(
                When(
                    batch__content_type=ContentType.objects.get_for_model(PurchaseItem),
                    then=Subquery(
                        PurchaseItem.objects
                        .filter(pk=OuterRef('batch__object_id'))
                        .values('unit_cost')[:1]
                    )
                ),
                When(
                    batch__content_type=ContentType.objects.get_for_model(StockAdjustment),
                    then=Subquery(
                        StockAdjustment.objects
                        .filter(pk=OuterRef('batch__object_id'))
                        .values('unit_cost')[:1]
                    )
                ),
                When(
                    batch__content_type=ContentType.objects.get_for_model(StockConversion),
                    then=Subquery(
                        StockConversion.objects
                        .filter(pk=OuterRef('batch__object_id'))
                        .values('unit_cost')[:1]
                    )
                ),
                default=Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).annotate(
            total_movement_cost=ExpressionWrapper(
                F('quantity') * F('cost_price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        
        total_cost = movements_with_cost.aggregate(
            total=Sum('total_movement_cost')
        )['total'] or 0

        return Decimal(total_cost)
    
    @property
    def gross_profit(self):
        return Decimal(self.line_total) - self.cost
    
    @property
    def profit_per_unit(self):
        return self.profit / self.quantity if self.quantity else 0
    
    @property
    def limited_by_stock(self):
        from inventory.models import StockMovement
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
    
    @property
    def name(self):
        return 'Sale'
