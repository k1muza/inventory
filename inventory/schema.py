import typing
import strawberry
import strawberry_django
from strawberry_django.optimizer import DjangoOptimizerExtension

from . import types
from . import models

@strawberry.type
class Query:
    @strawberry.field
    def products(self, info: strawberry.Info, name: str = None) -> typing.List[types.Product]:
        return models.Product.objects.filter(is_active=True)
    
    @strawberry.field
    def product(self, info: strawberry.Info, id: strawberry.ID) -> types.Product:
        return models.Product.objects.aget(id=id)
    
    @strawberry.field
    def purchases(self, info: strawberry.Info) -> typing.List[types.Purchase]:
        return models.Purchase.objects.all()
    
    @strawberry.field
    def sales(self, info: strawberry.Info) -> typing.List[types.Sale]:
        return models.Sale.objects.all()
    
    @strawberry.field
    def stock_adjustments(self, info: strawberry.Info) -> typing.List[types.StockAdjustment]:
        return models.StockAdjustment.objects.all()
    
    @strawberry.field
    def stock_conversions(self, info: strawberry.Info) -> typing.List[types.StockConversion]:
        return models.StockConversion.objects.all()

schema = strawberry.Schema(query=Query, extensions=[DjangoOptimizerExtension])
