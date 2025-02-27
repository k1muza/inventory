from django.core.management.base import BaseCommand
from django.db import models

from inventory.models import SaleItem


class Command(BaseCommand):
    help = 'Check and resolve sale quantities'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f'Checking {SaleItem.objects.count()} sale quantities'))
        count = 0
        for item in SaleItem.objects.all():
            movement_total_qnty = item.movements.aggregate(total_qnty=models.Sum('quantity'))['total_qnty']
            if movement_total_qnty != item.quantity and item.quantity > 0:
                self.stdout.write(
                    f"{item.sale.date}, {item.product}, {item.quantity}, {movement_total_qnty}"
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Found {count} discrepancies'))
        self.stdout.write(self.style.SUCCESS('Successfully checked sale quantities'))
