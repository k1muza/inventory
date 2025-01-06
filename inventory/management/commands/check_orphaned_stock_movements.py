from django.core.management.base import BaseCommand
from inventory.models import StockMovement

class Command(BaseCommand):
    help = 'Check for orphaned batches'

    def handle(self, *args, **options):
        for batch in StockMovement.objects.all():
            print(type(batch.linked_object))
        self.stdout.write(self.style.SUCCESS('Successfully checked for orphaned movements'))
