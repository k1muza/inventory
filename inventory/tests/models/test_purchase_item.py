import pytest
from datetime import datetime
from django.utils.timezone import make_aware

from inventory.models.stock_batch import StockBatch


@pytest.mark.django_db
def test_purchase_item_produces_batch(purchase_item_factory):
    purchase_item = purchase_item_factory(purchase__date=make_aware(datetime(2022, 1, 1)))
    assert StockBatch.objects.count() == 1
    batch = StockBatch.objects.first()
    assert batch.linked_object == purchase_item
    assert batch.date_received == purchase_item.purchase.date
    assert purchase_item.product.stock_value == purchase_item.line_total
