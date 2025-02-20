from django.core.management.base import BaseCommand

from inventory.models import StockAdjustment, StockBatch, SaleItem, PurchaseItem, StockConversion
from utils.decorators import timer

class Command(BaseCommand):
    help = 'Recreate transactions based on stock movements'

    @timer
    def handle(self, *args, **options):
        """
        Deletes all existing stock batches and then recreates them by saving
        all purchase items, stock adjustments, stock conversions, and sale items.
        Finally, outputs a success message indicating the completion of the batch 
        recreation process.
        """

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
