import pytest


@pytest.mark.django_db
def test_sale_profit(
    product_factory,
    purchase_item_factory,
    sale_item_factory,
    sale_factory,
):
    product = product_factory()
    purchase_item_factory(product=product, quantity=100, unit_cost=1.0)
    sale = sale_factory()
    sale_item_factory(product=product, quantity=100, unit_price=1.5, sale=sale)
    assert sale.gross_profit == 50
