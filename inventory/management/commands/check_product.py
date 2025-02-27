from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import ExpressionWrapper, OuterRef, Subquery, When, Case, Value, IntegerField, Sum, F, Q
from django.utils import timezone
from datetime import datetime
from django.utils.timezone import make_aware

from django.contrib.contenttypes.models import ContentType

from inventory.models import BatchMovement, Product, PurchaseItem, StockAdjustment, StockConversion
from inventory.models.sale_line_item import SaleItem


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--product-name', type=str)
        parser.add_argument('--date', type=str, default=timezone.now().strftime('%Y-%m-%d'))    

    def handle(self, *args, **options):
        product_name = options['product_name']
        date = make_aware(datetime.strptime(options['date'], '%Y-%m-%d'))

        product = Product.objects.get(name=product_name)
        
        qs = BatchMovement.objects.annotate(
            product_id=ExpressionWrapper(
                Case(
                    When(
                        content_type__model='saleitem',
                        then=Subquery(
                            SaleItem.objects.filter(
                                id=OuterRef('object_id')
                            ).values('product')[:1]
                        )
                    ),
                    When(
                        content_type__model='purchaseitem',
                        then=Subquery(
                            PurchaseItem.objects.filter(
                                id=OuterRef('object_id')
                            ).values('product')[:1]
                        )
                    ),
                    When(
                        content_type__model='stockadjustment',
                        then=Subquery(
                            StockAdjustment.objects.filter(
                                id=OuterRef('object_id')
                            ).values('product')[:1]
                        )
                    ),
                    When(
                        content_type__model='stockconversion',
                        movement_type=BatchMovement.MovementType.IN,
                        then=Subquery(
                            StockConversion.objects.filter(
                                id=OuterRef('object_id')
                            ).values('to_product')[:1]
                        )
                    ),
                    When(
                        content_type__model='stockconversion',
                        movement_type=BatchMovement.MovementType.OUT,
                        then=Subquery(
                            StockConversion.objects.filter(
                                id=OuterRef('object_id')
                            ).values('from_product')[:1]
                        )
                    ),
                    default=Value(None),
                ),
                output_field=IntegerField()
            )
        )

        qs = qs.filter(date__lt=date, product_id=product.pk)

        if qs.exists():
            self.stdout.write(self.style.SUCCESS(f'Product {product_name} has {qs.count()} batch movements'))
            
        total = qs.aggregate(total=Sum(
            Case(
                When(
                    movement_type=BatchMovement.MovementType.IN,
                    then=F('quantity')
                ),
                When(
                    movement_type=BatchMovement.MovementType.OUT,
                    then=-F('quantity')
                ),
                default=Value(Decimal('0.0'))
            )
        ))['total'] or Decimal('0.0')

        self.stdout.write(self.style.SUCCESS(f'Product {product_name} has {total} {product.unit}'))
