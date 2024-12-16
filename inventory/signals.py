from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import Expense, Lot, PurchaseItem, SaleItem, StockMovement, Transaction


@receiver(post_save, sender=PurchaseItem)
def create_stock_movement_purchase(sender, instance: PurchaseItem, created, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(PurchaseItem)
    StockMovement.objects.get_or_create(
        product=instance.product,
        movement_type='IN',
        quantity=instance.quantity,
        date=instance.purchase.date,
        content_type=purchase_ct,
        object_id=instance.id,
    )
    Transaction.objects.get_or_create(
        date=instance.purchase.date,
        transaction_type='PURCHASE',
        amount=instance.line_total,
        content_type=purchase_ct,
        object_id=instance.id,
    )
    Lot.objects.get_or_create(
        purchase_item=instance,
        cost_per_unit=instance.unit_price,
        quantity=instance.quantity,
        date_received=instance.purchase.date,
    )


@receiver(pre_delete, sender=PurchaseItem)
def delete_stock_movement_purchase(sender, instance: PurchaseItem, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(PurchaseItem)
    StockMovement.objects.filter(
        content_type=purchase_ct,
        object_id=instance.id,
    ).delete()
    Transaction.objects.filter(
        content_type=purchase_ct,
        object_id=instance.id,
    ).delete()
    Lot.objects.filter(
        purchase_item=instance,
    ).delete()


@receiver(post_save, sender=SaleItem)
def create_stock_movement_sale(sender, instance: SaleItem, created, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(SaleItem)
    StockMovement.objects.get_or_create(
        product=instance.product,
        movement_type='OUT',
        quantity=instance.quantity,
        date=instance.sale.date,
        content_type=purchase_ct,
        object_id=instance.id,
    )
    Transaction.objects.get_or_create(
        date=instance.sale.date,
        transaction_type='SALE',
        amount=instance.line_total,
        content_type=purchase_ct,
        object_id=instance.id,
    )


@receiver(post_save, sender=SaleItem)
def consume_lots(sender, instance: SaleItem, created, **kwargs):
    outstanding = instance.quantity
    for lot in instance.product.lots.all().order_by('date_received'):
        if lot.is_empty:
            continue
        
        outstanding = lot.consume(outstanding)
        
        if outstanding == 0:
            break


@receiver(post_save, sender=Expense)
def create_transaction_expense(sender, instance: Expense, created, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(Expense)
    Transaction.objects.get_or_create(
        date=instance.date,
        transaction_type='EXPENSE',
        amount=instance.amount,
        content_type=purchase_ct,
        object_id=instance.id,
    )
