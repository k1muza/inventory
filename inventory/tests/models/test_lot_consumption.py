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
    assert purchase_item.lot.quantity_remaining == 0
    assert purchase_item.lot.is_empty
    assert purchase_item.lot.movements.count() == 1
    assert purchase_item.lot.movements.last().date == sale_item.sale.date
