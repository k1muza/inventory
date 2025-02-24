import pytest


@pytest.mark.django_db
def test_lot_consumption_on_sale_date(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    purchase_item = purchase_item_factory(product=product, quantity=100)
    sale_item = sale_item_factory(product=product, quantity=100)
    assert purchase_item.batches.last().quantity_remaining == 0
    assert not purchase_item.batches.last().in_stock
    assert purchase_item.batches.last().movements.count() == 2
    assert purchase_item.batches.last().movements.last().date == sale_item.sale.date


@pytest.mark.django_db
def test_fifo_lot_consumption_on_sale(
    product_factory,
    purchase_item_factory, 
    sale_item_factory
):
    product = product_factory()
    first = purchase_item_factory(product=product, quantity=50)
    second = purchase_item_factory(product=product, quantity=50)
    third = purchase_item_factory(product=product, quantity=50)
    sale_item_factory(product=product, quantity=75)
    assert first.batches.last().quantity_remaining == 0
    assert second.batches.last().quantity_remaining == 25
    assert third.batches.last().quantity_remaining == 50
