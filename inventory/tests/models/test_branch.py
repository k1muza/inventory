import pytest
from django.contrib.contenttypes.models import ContentType
from inventory.models import StockBatch, PurchaseItem


@pytest.mark.django_db
def test_lot_creation_on_purchase_item(purchase_item_factory):
    purchase_item: PurchaseItem = purchase_item_factory()
    assert StockBatch.objects.count() == 1
    batch = StockBatch.objects.first()
    assert batch.linked_object == purchase_item
    assert batch.date_received == purchase_item.purchase.date


@pytest.mark.django_db
def test_batch_consumption_on_sale(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    purchase_item = purchase_item_factory(product=product, quantity=100)
    sale_item_factory(product=product, quantity=100)
    batch = StockBatch.objects.get(
        content_type=ContentType.objects.get_for_model(PurchaseItem),
        object_id=purchase_item.id
    )
    assert batch.quantity_remaining == 0
    assert batch.is_empty


@pytest.mark.django_db
def test_lot_movements_on_sale(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    first = purchase_item_factory(product=product, quantity=50)
    second = purchase_item_factory(product=product, quantity=50)
    third = purchase_item_factory(product=product, quantity=50)
    sale_item_factory(product=product, quantity=140)
    assert first.batch.quantity_remaining == 0
    assert second.batch.quantity_remaining == 0
    assert third.batch.quantity_remaining == 10
    assert not third.batch.is_empty


@pytest.mark.django_db
def test_lot_partial_consumption_on_sale(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    purchase_item = purchase_item_factory(product=product, quantity=100)
    sale_item_factory(product=product, quantity=51)
    assert purchase_item.batch.quantity_remaining == 49


@pytest.mark.parametrize(
    'cost_per_unit, price_per_unit, quantity, profit',
    [
        (1.0, 1.5, 100, 50),
        (1.0, 1.0, 100, 0),
        (1.0, 0.5, 100, -50),
        (1.0, 1.25, 100, 25),
    ]
)
@pytest.mark.django_db
def test_lot_profit(
    product_factory,
    purchase_item_factory, 
    sale_item_factory,
    cost_per_unit,
    price_per_unit,
    quantity,
    profit
):
    product = product_factory()
    purchase_item = purchase_item_factory(product=product, quantity=quantity, unit_cost=cost_per_unit)
    sale_item_factory(product=product, quantity=quantity, unit_price=price_per_unit)
    assert purchase_item.batch.profit == profit
