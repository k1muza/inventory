from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation

from inventory.models.stock_batch import StockBatch


class PurchaseItem(models.Model):
    purchase = models.ForeignKey('inventory.Purchase', related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('inventory.Product', on_delete=models.CASCADE, related_name='purchase_items')
    quantity = models.DecimalField(decimal_places=3, max_digits=15)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=6)

    batches = GenericRelation('inventory.StockBatch', related_query_name='purchase_item')

    def __str__(self):
        return f"{self.product.name} - {self.purchase.date.strftime('%Y-%m-%d')} - {self.quantity} x {self.unit_cost}"

    @property
    def line_total(self):
        return self.unit_cost * self.quantity if self.quantity and self.unit_cost else 0

    @property
    def name(self):
        return 'Purchase'

    @property
    def batch(self):
        return StockBatch.objects.get(
            content_type=ContentType.objects.get_for_model(PurchaseItem),
            object_id=self.id,
        )
