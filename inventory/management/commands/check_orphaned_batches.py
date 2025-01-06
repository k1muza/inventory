from django.core.management.base import BaseCommand
from inventory.models import StockBatch

class Command(BaseCommand):
    help = 'Check for orphaned batches'

    def handle(self, *args, **options):
        for batch in StockBatch.objects.all():
            if batch.linked_object is None:
                self.stdout.write(f"Orphaned batch: {batch}")
                # batch.delete()
        self.stdout.write(self.style.SUCCESS('Successfully checked for orphaned batches'))
