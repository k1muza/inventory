from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from .models import Cutting, Expense, Lot, LotMovement, PurchaseItem, SaleItem, StockMovement, Transaction


@receiver(post_save, sender=PurchaseItem)
def create_stock_movement_purchase(sender, instance: PurchaseItem, created, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(PurchaseItem)
    StockMovement.objects.get_or_create(
        content_type=purchase_ct,
        object_id=instance.id,
        defaults={
            "product": instance.product,
            "movement_type": 'IN',
            "quantity": instance.quantity,
            "date": instance.purchase.date,
        }
    )
    lot, _ = Lot.objects.get_or_create(
        purchase_item=instance,
        defaults=dict(
            date_received=instance.purchase.date,
        )
    )

    LotMovement.objects.get_or_create(
        lot=lot,
        date=instance.purchase.date,
        quantity=instance.quantity,
        movement_type=LotMovement.MovementType.IN,
        defaults=dict(
            description=f"Initial stock of {instance.quantity} {instance.product.unit} {instance.product.name}",
        )
    )

    if not instance.purchase.is_initial_stock:
        Transaction.objects.get_or_create(
            content_type=purchase_ct,
            object_id=instance.id,
            defaults={
                "date": instance.purchase.date,
                "transaction_type": 'PURCHASE',
                "amount": instance.line_total,
            }
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
        content_type=purchase_ct,
        object_id=instance.id,
        defaults=dict(
            product=instance.product,
            movement_type='OUT',
            quantity=instance.quantity,
            date=instance.sale.date,
        )
    )
    Transaction.objects.get_or_create(
        content_type=purchase_ct,
        object_id=instance.id,
        defaults=dict(
            date=instance.sale.date,
            transaction_type='SALE',
            amount=instance.line_total,
        )
    )


@receiver(pre_delete, sender=SaleItem)
def delete_stock_movement_sale(sender, instance: SaleItem, **kwargs):
    saleitem_ct = ContentType.objects.get_for_model(SaleItem)
    StockMovement.objects.filter(
        content_type=saleitem_ct,
        object_id=instance.id,
    ).delete()
    Transaction.objects.filter(
        content_type=saleitem_ct,
        object_id=instance.id,
    ).delete()
    LotMovement.objects.filter(
        content_type=saleitem_ct,
        object_id=instance.id,
    ).delete()


@receiver(post_save, sender=SaleItem)
@transaction.atomic
def consume_lots(sender, instance: SaleItem, created, **kwargs):
    outstanding = instance.quantity
    for lot in instance.product.lots.all().order_by('date_received'):
        if lot.is_empty:
            continue
        
        outstanding = lot.consume(outstanding, instance)
        
        if outstanding <= 0:
            break


@receiver(post_save, sender=Expense)
def create_transaction_expense(sender, instance: Expense, created, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(Expense)
    Transaction.objects.get_or_create(
        content_type=purchase_ct,
        object_id=instance.id,
        defaults=dict(
            date=instance.date,
            transaction_type='EXPENSE',
            amount=instance.amount,
        )
    )

@receiver(pre_delete, sender=Expense)
def delete_transaction_expense(sender, instance: Expense, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(Expense)
    Transaction.objects.filter(
        content_type=purchase_ct,
        object_id=instance.id,
    ).delete()


@receiver(post_save, sender=Cutting)
def create_stock_movement_cutting(sender, instance: Cutting, created, **kwargs):
    cutting_ct = ContentType.objects.get_for_model(Cutting)
    StockMovement.objects.get_or_create(
        content_type=cutting_ct,
        object_id=instance.id,
        defaults=dict(
            product=instance.lot.purchase_item.product,
            movement_type='OUT',
            quantity=instance.starting_weight - instance.ending_weight,
            date=instance.date,
        )
    )
    Transaction.objects.get_or_create(
        content_type=cutting_ct,
        object_id=instance.id,
        defaults=dict(
            date=instance.date,
            transaction_type='EXPENSE',
            amount=instance.total_cost,
        )
    )
    LotMovement.objects.get_or_create(
        lot=instance.lot,
        date=instance.date,
        quantity=instance.starting_weight - instance.ending_weight,
        movement_type=LotMovement.MovementType.OUT,
        defaults=dict(
            description=f"Cutting {instance.starting_weight} {instance.lot.purchase_item.product.unit} {instance.lot.purchase_item.product.name}",
        )
    )
