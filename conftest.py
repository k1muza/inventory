# conftest.py
import pytest
from pytest_factoryboy import register

from inventory.tests.factory import BatchFactory, ProductFactory, PurchaseItemFactory, SaleFactory, SaleItemFactory, StockAdjustmentFactory, StockConversionFactory

register(ProductFactory)  # This creates a `product_factory` fixture.
register(PurchaseItemFactory)  # This creates a `purchase_item_factory` fixture.
register(SaleItemFactory)  # This creates a `sale_item_factory` fixture.
register(SaleFactory) # This creates a `sale_factory` fixture.
register(BatchFactory)  # This creates a `batch_factory` fixture.
register(StockConversionFactory)  # This creates a `stock_conversion_factory` fixture.
register(StockAdjustmentFactory)  # This creates a `stock_adjustment_factory` fixture.
