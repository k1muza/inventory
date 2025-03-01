import pytest
from datetime import datetime
from django.utils import timezone
from inventory.models.stock_batch import StockBatch


@pytest.mark.django_db
def test_stock_conversion_consumes_batch(
    product_factory,
    purchase_item_factory,
    stock_conversion_factory
):
    from_product = product_factory(name="Beef", unit="kg")
    to_product = product_factory(name="Beef bones", unit="kg")

    purchase_item = purchase_item_factory(product=from_product, quantity=100, purchase__date=datetime(2022, 1, 1))
    stock_conversion = stock_conversion_factory(
        from_product=from_product,
        to_product=to_product,
        unit_cost=purchase_item.unit_cost,
        quantity=20,
        date=purchase_item.purchase.date + timezone.timedelta(days=1)
    )

    assert StockBatch.objects.count() == 2

    first_batch = StockBatch.objects.earliest('date_received')
    second_batch = StockBatch.objects.latest('date_received')

    assert first_batch.product == from_product
    assert second_batch.product == to_product
    assert stock_conversion.batches.count() == 1
    assert stock_conversion.batches.first().product == to_product
    assert second_batch.quantity_remaining == 20
    assert first_batch.quantity_remaining == 80
    assert from_product.batch_based_stock_level == 80
    assert from_product.stock_value == 80 * purchase_item.unit_cost
    assert to_product.stock_value == 20 * purchase_item.unit_cost
