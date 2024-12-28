# conftest.py
import pytest
from pytest_factoryboy import register

from inventory.tests.factory import CuttingFactory, LotFactory, ProductFactory, PurchaseItemFactory, SaleFactory, SaleItemFactory

register(ProductFactory)  # This creates a `product_factory` fixture.
register(PurchaseItemFactory)  # This creates a `purchase_item_factory` fixture.
register(SaleItemFactory)  # This creates a `sale_item_factory` fixture.
register(SaleFactory) # This creates a `sale_factory` fixture.
register(LotFactory)  # This creates a `lot_factory` fixture.
register(CuttingFactory)  # This creates a `cutting_factory` fixture.
