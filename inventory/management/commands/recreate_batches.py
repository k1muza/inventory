from django.core.management.base import BaseCommand

from inventory.models import StockAdjustment, StockBatch, SaleItem, PurchaseItem, StockConversion

class Command(BaseCommand):
    help = 'Recreate transactions based on stock movements'

    def handle(self, *args, **options):
        StockBatch.objects.all().delete()

        for item in PurchaseItem.objects.all():
            item.save()

        for item in StockAdjustment.objects.all():
            item.save()

        for item in StockConversion.objects.all():
            item.save()

        for item in SaleItem.objects.all():
            item.save()

        self.stdout.write(self.style.SUCCESS('Successfully recreated purchase batches'))
