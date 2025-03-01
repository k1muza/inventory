import uuid
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase'),
        ('EXPENSE', 'Expense'),
        ('ADJUSTMENT', 'Adjustment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateTimeField(default=timezone.now)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # GenericForeignKey fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ['content_type', 'object_id']
        ordering = ['-date']

    @property
    def item(self):
        from inventory.models import SaleItem, PurchaseItem
        if self.linked_object and hasattr(self.linked_object, 'product'):
            if isinstance(self.linked_object, SaleItem):
                return f"{self.linked_object.product.name} ({self.linked_object.unit_price} x {self.linked_object.quantity})"
            elif isinstance(self.linked_object, PurchaseItem):
                return f"{self.linked_object.product.name} ({self.linked_object.unit_cost} x {self.linked_object.quantity})"
        elif self.linked_object and hasattr(self.linked_object, 'description'):
            return self.linked_object.description
        return f"{self.transaction_type} - {self.amount}"
