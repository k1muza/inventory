from django.db import models
from django.utils import timezone


class Purchase(models.Model):
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    is_initial_stock = models.BooleanField(default=False)

    def __str__(self):
        return f"Purchase {self.id} on {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def total_amount(self):
        return sum(item.unit_cost*item.quantity for item in self.items.all())
