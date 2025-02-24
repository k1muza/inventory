from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class BatchMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'
        ADJUSTMENT = 'ADJ', 'Adjustment'
        
    batch = models.ForeignKey('inventory.StockBatch', on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=10, choices=MovementType.choices)
    quantity = models.DecimalField(decimal_places=3, max_digits=15)
    date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255, blank=True, null=True)

    # GenericForeignKey fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name_plural = 'Batch Movements'
        constraints = [
            models.CheckConstraint(
                name='positive_quantity',
                check=models.Q(quantity__gt=0)
            )
        ]
    
    def __str__(self):
        return f"{self.batch.linked_object.product.name} - {self.quantity} - {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def cost(self):
        return self.quantity * self.batch.unit_cost
    
    @property
    def revenue(self):
        return 0 # TODO: Implement this
    
    @property
    def profit(self):
        return self.revenue - self.cost
