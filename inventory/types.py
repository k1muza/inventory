from decimal import Decimal
import typing
import strawberry_django
import strawberry

from . import models


@strawberry_django.type(models.Product)
class Product: 
    id: strawberry.ID
    name: typing.Optional[str]
    description: typing.Optional[str]
    unit_price: typing.Optional[Decimal]
    unit_cost: typing.Optional[Decimal]
    minimum_stock_level: typing.Optional[int]
    unit: typing.Optional[str]


@strawberry_django.type(models.Purchase)
class Purchase:
    id: strawberry.ID
    date: typing.Optional[str]
    notes: typing.Optional[str]
    items: typing.List['PurchaseItem']


@strawberry_django.type(models.PurchaseItem)
class PurchaseItem:
    id: strawberry.ID
    product: typing.Optional[Product]
    quantity: typing.Optional[Decimal]
    unit_cost: typing.Optional[Decimal]


@strawberry_django.type(models.Sale)
class Sale:
    id: strawberry.ID
    date: typing.Optional[str]
    notes: typing.Optional[str]
    items: typing.List['SaleItem']


@strawberry_django.type(models.SaleItem)
class SaleItem:
    id: strawberry.ID
    product: typing.Optional[Product]
    quantity: typing.Optional[Decimal]
    unit_price: typing.Optional[Decimal]


@strawberry_django.type(models.StockAdjustment)
class StockAdjustment:
    id: strawberry.ID
    product: typing.Optional[Product]
    quantity: typing.Optional[Decimal]
    unit_cost: typing.Optional[Decimal]
    date: typing.Optional[str]
    reason: typing.Optional[str]


@strawberry_django.type(models.StockConversion)
class StockConversion:
    id: strawberry.ID
    from_product: typing.Optional[Product]
    to_product: typing.Optional[Product]
    quantity: typing.Optional[Decimal]
    unit_cost: typing.Optional[Decimal]
    date: typing.Optional[str]
    reason: typing.Optional[str]
