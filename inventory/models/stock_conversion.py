from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation


class StockConversion(models.Model):
    from_product = models.ForeignKey('inventory.Product', related_name='conversions_from', on_delete=models.CASCADE)
    to_product = models.ForeignKey('inventory.Product', related_name='conversions_to', on_delete=models.CASCADE)
    quantity = models.DecimalField(decimal_places=3, max_digits=15)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=6)
    date = models.DateTimeField(default=timezone.now)
    reason = models.TextField(blank=True)

    movements = GenericRelation('inventory.BatchMovement', related_query_name='adjustment') # Finish this 
    batches = GenericRelation('inventory.StockBatch', related_query_name='adjustment')

    def __str__(self):
        return f"{self.from_product.name} - {self.to_product.name} - {self.quantity}"
    
    class Meta:
        verbose_name_plural = 'Stock Conversions'

    @property
    def product(self):
        return self.to_product

