from django.core.management.base import BaseCommand

from inventory.models import StockAdjustment, StockBatch, SaleItem, PurchaseItem, StockConversion, BatchMovement, StockMovement
from utils.decorators import timer


class Command(BaseCommand):
    help = 'Recreate transactions based on stock movements'

    @timer
    def save_purchase_items(self):
        for item in PurchaseItem.objects.all():
            item.save()

    @timer
    def save_stock_adjustments(self):
        for item in StockAdjustment.objects.all():
            item.save()

    @timer
    def save_stock_conversions(self):
        for item in StockConversion.objects.all():
            item.save()

    @timer
    def save_sale_items(self):
        for item in SaleItem.objects.all():
            item.save()

    @timer
    def handle(self, *args, **options):
        """
        Deletes all existing stock batches and then recreates them by saving
        all purchase items, stock adjustments, stock conversions, and sale items.
        Finally, outputs a success message indicating the completion of the batch
        recreation process.
        """

        batches_count = StockBatch.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Found {batches_count} stock batches'))
        StockBatch.objects.all().delete()
        StockMovement.objects.all().delete()

        purchase_item_count = PurchaseItem.objects.count()
        stock_adjustment_count = StockAdjustment.objects.count()
        stock_conversion_count = StockConversion.objects.count()
        sale_item_count = SaleItem.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Found {purchase_item_count} purchase items, {stock_adjustment_count} stock adjustments, {stock_conversion_count} stock conversions, and {sale_item_count} sale items'
            )
        )

        self.save_purchase_items()
        self.save_stock_adjustments()
        self.save_stock_conversions()
        self.save_sale_items()

        batches_count = StockBatch.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Recreated {batches_count} stock batches'))

        stock_movements_count = StockMovement.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Recreated {stock_movements_count} stock movements'))

        batch_movements_count = BatchMovement.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Recreated {batch_movements_count} batch movements'))

        self.stdout.write(self.style.SUCCESS('Done'))
