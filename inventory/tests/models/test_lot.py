import pytest
from inventory.models import Lot, PurchaseItem


@pytest.mark.django_db
def test_lot_creation_on_purchase_item(purchase_item_factory):
    purchase_item: PurchaseItem = purchase_item_factory()
    assert Lot.objects.count() == 1
    lot = Lot.objects.first()
    assert lot.purchase_item == purchase_item
    assert lot.date_received == purchase_item.purchase.date


@pytest.mark.django_db
def test_lot_consumption_on_sale(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    purchase_item = purchase_item_factory(product=product, quantity=100)
    sale_item_factory(product=product, quantity=100)
    assert purchase_item.lot.quantity_remaining == 0
    assert purchase_item.lot.is_empty


@pytest.mark.django_db
def test_lot_consumptions_on_sale(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    first = purchase_item_factory(product=product, quantity=50)
    second = purchase_item_factory(product=product, quantity=50)
    third = purchase_item_factory(product=product, quantity=50)
    sale_item_factory(product=product, quantity=140)
    assert first.lot.quantity_remaining == 0
    assert second.lot.quantity_remaining == 0
    assert third.lot.quantity_remaining == 10
    assert not third.lot.is_empty


@pytest.mark.django_db
def test_lot_partial_consumption_on_sale(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    purchase_item = purchase_item_factory(product=product, quantity=100)
    sale_item_factory(product=product, quantity=51)
    assert purchase_item.lot.quantity_remaining == 49


@pytest.mark.parametrize(
    'cost_per_unit, price_per_unit, quantity, profit',
    [
        (1.0, 1.5, 100, 50),
        (1.0, 1.0, 100, 0),
        (1.0, 0.5, 100, -50),
        (1.0, 1.0, 0, 0),
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
    assert purchase_item.lot.profit == profit
