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
    latest_batch = purchase_item.batches.latest('date_received')
    assert latest_batch.quantity_remaining == 0
    assert not latest_batch.in_stock
    assert latest_batch.movements.count() == 2
    assert latest_batch.movements.latest('date').date == sale_item.sale.date


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
    assert first.batches.latest('date_received').quantity_remaining == 0
    assert second.batches.latest('date_received').quantity_remaining == 25
    assert third.batches.latest('date_received').quantity_remaining == 50
