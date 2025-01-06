from django.core.management.base import BaseCommand

from inventory.models import SaleItem

class Command(BaseCommand):
    help = 'Check and resolve sale quantities'

    def handle(self, *args, **options):
        for item in SaleItem.objects.all():
            movement_qnty = sum([m.quantity for m in item.movements.all()])
            if movement_qnty != item.quantity:
                self.stdout.write(
                    f"{item.sale.date}, {item.product}, {item.quantity}, {movement_qnty}"
                )
        self.stdout.write(self.style.SUCCESS('Successfully checked sale quantities'))
