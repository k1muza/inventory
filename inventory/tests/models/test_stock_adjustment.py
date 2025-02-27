import pytest
from datetime import datetime
from inventory.models.batch_movement import BatchMovement

from inventory.models import StockBatch


@pytest.mark.django_db
def test_stock_adjustment_increases_stock(stock_adjustment_factory):
    stock_adjustment_factory(
        quantity=10,
        unit_cost=1.0
    )
    assert StockBatch.objects.count() == 1
    batch = StockBatch.objects.first()
    assert batch.quantity_remaining == 10
    assert BatchMovement.objects.count() == 1
    movement = BatchMovement.objects.first()
    assert movement.batch == batch
    assert movement.movement_type == BatchMovement.MovementType.IN
    assert movement.quantity == 10


@pytest.mark.django_db
def test_stock_adjustment_decreases_stock(product_factory, stock_adjustment_factory, purchase_item_factory):
    product = product_factory()
    purchase_item_factory(
        product=product,
        quantity=10,
        unit_cost=1.0,
        purchase__date=datetime(2022, 1, 1)
    )
    stock_adjustment_factory(
        product=product,
        quantity=-5,
        unit_cost=1.0,
        date=datetime(2022, 1, 2)
    )
    assert StockBatch.objects.count() == 1
    batch = StockBatch.objects.first()
    assert batch.quantity_remaining == 5
    assert batch.unit_cost == 1.0
    assert BatchMovement.objects.count() == 2
    movement = BatchMovement.objects.last()
    assert movement.batch == batch
    assert movement.movement_type == BatchMovement.MovementType.OUT
    assert movement.quantity == 5
