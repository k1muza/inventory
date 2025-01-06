from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation


class Expense(models.Model):
    date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    category = models.CharField(max_length=100, blank=True)

    transactions = GenericRelation('inventory.Transaction', related_query_name='expense')

    def __str__(self):
        return f"{self.description} - {self.amount}"
