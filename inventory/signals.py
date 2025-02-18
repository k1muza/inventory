from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from .models import Expense, StockBatch, BatchMovement, PurchaseItem, SaleItem, StockAdjustment, StockConversion, StockMovement, Transaction


@receiver(post_save, sender=PurchaseItem)
def on_purchase_item_save(sender, instance: PurchaseItem, created, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(PurchaseItem)
    StockMovement.objects.update_or_create(
        content_type=purchase_ct,
        object_id=instance.id,
        defaults={
            "product": instance.product,
            "movement_type": 'IN',
            "quantity": instance.quantity,
            "date": instance.purchase.date,
        }
    )
    
    StockBatch.objects.update_or_create(
        content_type=purchase_ct,
        object_id=instance.id,
        defaults=dict(
            date_received=instance.purchase.date,
        )
    )

    if not instance.purchase.is_initial_stock:
        Transaction.objects.update_or_create(
            content_type=purchase_ct,
            object_id=instance.id,
            defaults={
                "date": instance.purchase.date,
                "transaction_type": 'PURCHASE',
                "amount": instance.line_total,
            }
        )


@receiver(pre_delete, sender=PurchaseItem)
def on_purchase_item_delete(sender, instance: PurchaseItem, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(PurchaseItem)
    StockMovement.objects.filter(
        content_type=purchase_ct,
        object_id=instance.id,
    ).delete()
    Transaction.objects.filter(
        content_type=purchase_ct,
        object_id=instance.id,
    ).delete()
    StockBatch.objects.filter(
        content_type=purchase_ct,
        object_id=instance.id,
    ).delete()


@receiver(post_save, sender=SaleItem)
def on_sale_item_save(sender, instance: SaleItem, created, **kwargs):
    purchase_ct = ContentType.objects.get_for_model(SaleItem)
    StockMovement.objects.update_or_create(
        content_type=purchase_ct,
        object_id=instance.id,
        defaults=dict(
            product=instance.product,
            movement_type='OUT',
            quantity=instance.quantity,
            date=instance.sale.date,
        )
    )
    instance.transactions.update_or_create(
        defaults=dict(
            date=instance.sale.date,
            transaction_type='SALE',
            amount=instance.line_total,
        )
    )


@receiver(pre_delete, sender=SaleItem)
def on_sale_item_delete(sender, instance: SaleItem, **kwargs):
    saleitem_ct = ContentType.objects.get_for_model(SaleItem)
    StockMovement.objects.filter(
        content_type=saleitem_ct,
        object_id=instance.id,
    ).delete()
    instance.transactions.all().delete()
    instance.movements.all().delete()


@receiver(post_save, sender=SaleItem)
@transaction.atomic
def consume_batches(sender, instance: SaleItem, created, **kwargs):
    instance.movements.all().delete()
    try:
        instance.product.consume(instance.quantity, instance)
    except ValueError as e:
        print(f"Error consuming product {instance.product}: {e}")


@receiver(post_save, sender=Expense)
def on_expense_save(sender, instance: Expense, created, **kwargs):
    instance.transactions.update_or_create(
        defaults=dict(
            date=instance.date,
            transaction_type='EXPENSE',
            amount=instance.amount,
        )
    )


@receiver(pre_delete, sender=Expense)
def on_expense_delete(sender, instance: Expense, **kwargs):
    instance.transactions.all().delete()


@receiver(post_save, sender=StockAdjustment)
def on_stock_adjustment_save(sender, instance: StockAdjustment, created, **kwargs):
    instance.movements.all().delete()
    instance.batches.all().delete()

    adjustment_ct = ContentType.objects.get_for_model(StockAdjustment)
    
    if instance.quantity > 0:
        instance.batches.get_or_create(
            defaults=dict(
                date_received=instance.date,
            )
        )
        StockMovement.objects.update_or_create(
            content_type=adjustment_ct,
            object_id=instance.id,
            product=instance.product,
            movement_type='IN',
            defaults=dict(
                quantity=instance.quantity,
                date=instance.date,
            )
        )
    else:
        StockMovement.objects.update_or_create(
            content_type=adjustment_ct,
            object_id=instance.id,
            product=instance.product,
            movement_type='OUT',
            defaults=dict(
                quantity=-instance.quantity,
                date=instance.date,
            )
        )
        instance.product.consume(abs(instance.quantity), instance)


@receiver(pre_delete, sender=StockAdjustment)
def on_stock_adjustment_delete(sender, instance: StockAdjustment, **kwargs):
    instance.movements.all().delete()
    instance.batches.all().delete()


@receiver(post_save, sender=StockConversion)
def on_stock_conversion_save(sender, instance: StockConversion, created, **kwargs):
    instance.movements.all().delete()
    instance.batches.all().delete()

    try:
        instance.from_product.consume(instance.quantity, instance)
    except ValueError as e:
        raise ValueError(f"Error consuming product {instance.from_product}: {e}")

    conversion_ct = ContentType.objects.get_for_model(StockConversion)
    StockMovement.objects.update_or_create(
        content_type=conversion_ct,
        object_id=instance.id,
        product=instance.from_product,
        defaults=dict(
            movement_type='OUT',
            quantity=instance.quantity,
            date=instance.date,
        )
    )
    StockMovement.objects.update_or_create(
        content_type=conversion_ct,
        object_id=instance.id,
        product=instance.to_product,
        defaults=dict(
            movement_type='IN',
            quantity=instance.quantity,
            date=instance.date,
        )
    )
    StockBatch.objects.update_or_create(
        content_type=conversion_ct,
        object_id=instance.id,
        defaults=dict(
            date_received=instance.date,
        )
    )


@receiver(pre_delete, sender=StockConversion)
def on_stock_conversion_delete(sender, instance: StockConversion, **kwargs):
    instance.movements.all().delete()
    instance.batches.all().delete()


@receiver(post_save, sender=StockBatch)
def on_stock_batch_save(sender, instance: StockBatch, created, **kwargs):
    BatchMovement.objects.update_or_create(
        batch=instance,
        quantity=instance.linked_object.quantity,
        movement_type=BatchMovement.MovementType.IN,
        defaults=dict(
            date=instance.date_received,
            description=f"Creation of {instance.linked_object.quantity} {instance.linked_object.product.unit} {instance.linked_object.product.name}",
        )
    )
