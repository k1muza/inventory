from django.core.management.base import BaseCommand

from inventory.models import StockMovement, Transaction, SaleItem, PurchaseItem, Expense


class Command(BaseCommand):
    help = 'Recreate transactions based on stock movements'

    def handle(self, *args, **options):
        Transaction.objects.all().delete()
        StockMovement.objects.all().delete()

        for item in SaleItem.objects.all():
            item.save()

        for item in PurchaseItem.objects.all():
            item.save()

        for expense in Expense.objects.all():
            expense.save()

        self.stdout.write(self.style.SUCCESS('Successfully recreated transactions'))
