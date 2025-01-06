from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.db.models import F, ExpressionWrapper, DecimalField
from django.contrib.contenttypes.models import ContentType
from django.db.models import Case, When, Value, Subquery, OuterRef, Sum


class Sale(models.Model):
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Sale {self.id} on {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def total_amount(self):
        return sum(item.unit_price*item.quantity for item in self.items.all())
    
    @property
    def movements(self):
        from inventory.models import BatchMovement, SaleItem
        saleitem_ct = ContentType.objects.get_for_model(SaleItem)
        return BatchMovement.objects.filter(
            content_type=saleitem_ct,
            object_id__in=[i['id'] for i in self.items.values('id')]
        )
    
    @property
    def cost_of_goods_sold(self):
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
        
        # Sum those costs across all movements
        total_cost = movements_with_cost.aggregate(
            total=Sum('total_movement_cost')
        )['total'] or 0
        
        return total_cost
        
    @property
    def gross_profit(self):
        total_revenue = Decimal('0.0')
        for movement in self.movements.all():
            # Check if movement.linked_object is a SaleItem
            if movement.linked_object and type(movement.linked_object).__name__ == 'SaleItem':
                sale_item = movement.linked_object
                total_revenue += (movement.quantity * sale_item.unit_price)

        return total_revenue - self.cost_of_goods_sold
    
    @property
    def gross_margin(self):
        return self.gross_profit / self.total_amount if self.total_amount else 0

