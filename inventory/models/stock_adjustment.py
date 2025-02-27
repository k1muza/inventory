from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation


class StockAdjustment(models.Model):
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE, related_name='adjustments')
    quantity = models.DecimalField(decimal_places=3, max_digits=15)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=6)
    date = models.DateTimeField(default=timezone.now)
    reason = models.TextField(blank=True)

    movements = GenericRelation('inventory.BatchMovement', related_query_name='adjustment')  # Finish this
    batches = GenericRelation('inventory.StockBatch', related_query_name='adjustment')

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"

    class Meta:
        verbose_name_plural = 'Stock Adjustments'

    @property
    def name(self):
        return 'Adjustment'
