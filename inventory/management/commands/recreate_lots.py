from django.core.management.base import BaseCommand

from inventory.models import Cutting, Lot, SaleItem, PurchaseItem, StockMovement

class Command(BaseCommand):
    help = 'Recreate transactions based on stock movements'

    def handle(self, *args, **options):
        Lot.objects.all().delete()

        for item in PurchaseItem.objects.all():
            item.save()

        for item in Cutting.objects.all():
            item.save()

        for item in SaleItem.objects.all():
            item.save()

        self.stdout.write(self.style.SUCCESS('Successfully recreated purchase lots'))
