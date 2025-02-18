from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import F, Sum, DecimalField, ExpressionWrapper, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.contrib.contenttypes.fields import GenericRelation


class StockBatch(models.Model):
    date_received = models.DateTimeField(default=timezone.now)

    # GenericForeignKey fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['date_received', 'id']
        verbose_name_plural = 'Stock Batches'

    def __str__(self):
        return f"{self.date_received.date()} - {self.linked_object.product.name} - {self.linked_object.quantity} {self.linked_object.product.unit}"
    
    @property
    def product(self):
        return self.linked_object.product

    @property
    def quantity(self):
        return self.linked_object.quantity
    
    @property
    def unit_cost(self):
        return self.linked_object.unit_cost
    
    @property
    def quantity_remaining(self):
        return self.get_quantity_remaining()
    
    @property
    def quantity_remaining_cost(self):
        return self.quantity_remaining * self.unit_cost
    
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
        from inventory.models import BatchMovement, SaleItem
        movements = self.movements.filter(movement_type=BatchMovement.MovementType.OUT)

        movements = movements.annotate(
            sale_price=Subquery(
                SaleItem.objects
                .filter(pk=OuterRef('object_id'))
                .values('unit_price')[:1]
            )
        )

        revenue_aggregation = (
            movements
            .filter(
                content_type=ContentType.objects.get_for_model(SaleItem)
            )  
            .annotate(
                total_revenue=ExpressionWrapper(
                    F('quantity') * F('sale_price'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )
            .aggregate(revenue=Sum('total_revenue'))
        )['revenue'] or 0

        quantity_aggregation = (
            movements.filter(
                content_type=ContentType.objects.get_for_model(SaleItem)
            )
            .aggregate(total_quantity=Sum('quantity'))['total_quantity']
            or 0
        )

        unit_cost = self.linked_object.unit_cost
        return revenue_aggregation - (unit_cost * Decimal(quantity_aggregation))  
    
    def consume(self, quantity, associated_item):
        from inventory.models import BatchMovement
        ear_marked = min(quantity, self.quantity_remaining)
        ct = ContentType.objects.get_for_model(type(associated_item))
        
        if self.quantity_remaining > 0 and ear_marked > 0:
            self.movements.create(
                batch=self, 
                content_type=ct,
                object_id=associated_item.id if associated_item else None,
                quantity=ear_marked, 
                date=associated_item.date or timezone.now(),
                movement_type=BatchMovement.MovementType.OUT,
            )
        return quantity - ear_marked

    def get_quantity_remaining(self, date=None):
        from inventory.models import BatchMovement
        # Sum all 'IN' movements prior to or at `date`

        if not date:
            date = timezone.now()
            
        total_in = self.movements.filter(
            date__lt=date,
            movement_type=BatchMovement.MovementType.IN
        ).aggregate(
            total=Coalesce(Sum('quantity'), Decimal(0.0))
        )['total']

        # Sum all 'OUT' movements prior to or at `date`
        total_out = self.movements.filter(
            date__lt=date,
            movement_type=BatchMovement.MovementType.OUT
        ).aggregate(
            total=Coalesce(Sum('quantity'), Decimal(0.0))
        )['total']

        return total_in - total_out
