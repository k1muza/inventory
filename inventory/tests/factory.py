import factory

from inventory.models import StockBatch, Product, Purchase, Sale, SaleItem

class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Faker('word')
    selling_price = factory.Faker('pydecimal', left_digits=1, right_digits=2, positive=True)
    purchase_price = factory.Faker('pydecimal', left_digits=1, right_digits=2, positive=True)


class PurchaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Purchase

    notes = factory.Faker('sentence')


class PurchaseItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'inventory.PurchaseItem'

    purchase = factory.SubFactory(PurchaseFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = factory.Faker('random_int', min=1, max=100)
    unit_cost = factory.Faker('pydecimal', left_digits=1, right_digits=2, positive=True)


class SaleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Sale

    notes = factory.Faker('sentence')


class SaleItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SaleItem

    sale = factory.SubFactory(SaleFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = factory.Faker('random_int', min=1, max=100)
    unit_price = factory.Faker('pydecimal', left_digits=1, right_digits=2, positive=True)



class BatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StockBatch

    purchase_item = factory.SubFactory(PurchaseItemFactory)
