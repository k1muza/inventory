import pytest


@pytest.mark.parametrize(
    'unit_cost, unit_price, quantity, profit',
    [
        (1.0, 1.5, 100, 50),
        (1.0, 1.0, 100, 0),
        (1.0, 0.5, 100, -50),
        (1.0, 1.0, 0, 0),
        (1.0, 1.25, 100, 25),
    ]
)
@pytest.mark.django_db
def test_saleitem_profit(
    product_factory,
    purchase_item_factory, 
    sale_item_factory,
    unit_cost,
    unit_price,
    quantity,
    profit
):
    product = product_factory()
    purchase_item_factory(
        product=product, 
        quantity=quantity, 
        unit_cost=unit_cost
    )
    sale_item = sale_item_factory(
        product=product, 
        quantity=quantity, 
        unit_price=unit_price
    )
    assert sale_item.profit == profit


@pytest.mark.parametrize(
    'purchases, unit_price, sale_quantity, profit',
    [
        (
            [
                (100, 1.0),
            ],
            1.5,
            20,
            10
        ), # Partial consumption
        (
            [
                (50, 1.0),
                (50, 1.20),
            ],
            1.5,
            100,
            40
        ), # Full consumption with different purchase prices
        (
            [
                (50, 1.0),
                (50, 1.20),
            ],
            1.0,
            100,
            -10
        ), # Full consumption with different purchase prices and loss
        (
            [
                (50, 1.0),
                (50, 1.20),
                (40, 1.25),
            ],
            1.25,
            100,
            15
        ), # Untouched lot with previous consumed lots
    ]
)
@pytest.mark.django_db
def test_saleitem_profit_multiple_consumptions(
    product_factory,
    purchase_item_factory, 
    sale_item_factory,
    purchases,
    unit_price,
    sale_quantity,
    profit
):
    product = product_factory()
    for quantity, unit_cost in purchases:
        purchase_item_factory(
            product=product, 
            quantity=quantity, 
            unit_cost=unit_cost
        )
    
    sale_item = sale_item_factory(
        product=product, 
        quantity=sale_quantity, 
        unit_price=unit_price
    )
    assert sale_item.profit == profit
