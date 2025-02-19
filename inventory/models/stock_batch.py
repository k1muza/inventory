from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import F, Sum, DecimalField, ExpressionWrapper, Subquery, OuterRef, Value, Case, When
from django.db.models.functions import Coalesce


class StockBatchQuerySet(models.QuerySet):
    def annotate_batch_quantities(self):
        """
        Annotate the queryset with total 'IN' and 'OUT' batch movement quantities.

        This function adds two annotations to the given queryset:
        - total_in: The sum of quantities for movements with type 'IN'.
        - total_out: The sum of quantities for movements with type 'OUT'.

        Both annotations make use of Coalesce to ensure a default value of 0.0 is 
        returned if there are no matching movements of the respective type.
        """

        from inventory.models import BatchMovement
        return self.annotate(
            total_in=Coalesce(
                Sum(
                    Case(
                        When(movements__movement_type=BatchMovement.MovementType.IN, then=F('movements__quantity')),
                        default=Value(Decimal('0.0')),
                    ),
                ),
                Value(Decimal('0.0')),
            ),
            total_out=Coalesce(
                Sum(
                    Case(
                        When(movements__movement_type=BatchMovement.MovementType.OUT, then=F('movements__quantity')),
                        default=Value(Decimal('0.0')),
                    )
                ),
                Value(Decimal('0.0')),
            ),
        )
    
    def annotate_batch_costs(self):
        """
        Annotate the queryset with the effective unit cost based on the linked object type.

        This function adds an annotation to the queryset:
        - effective_unit_cost: The unit cost determined by the linked content type.
        The annotation is calculated using a Case expression that evaluates the
        content type of each object in the queryset. The effective unit cost is 
        retrieved from related models such as PurchaseItem, StockAdjustment, or 
        StockConversion using a Subquery.

        The default value of the effective unit cost is set to 0. The annotation 
        uses a DecimalField with a precision of up to 15 digits and 6 decimal places.
        """

        from inventory.models import PurchaseItem, StockAdjustment, StockConversion

        return self.annotate(
            effective_unit_cost=Case(
                When(
                    content_type=ContentType.objects.get_for_model(PurchaseItem), 
                    then=Subquery(PurchaseItem.objects.filter(pk=OuterRef('object_id')).values('unit_cost')[:1])
                ),
                When(
                    content_type=ContentType.objects.get_for_model(StockAdjustment), 
                    then=Subquery(StockAdjustment.objects.filter(pk=OuterRef('object_id')).values('unit_cost')[:1])
                ),
                When(
                    content_type=ContentType.objects.get_for_model(StockConversion), 
                    then=Subquery(StockConversion.objects.filter(pk=OuterRef('object_id')).values('unit_cost')[:1])
                ),
                default=Value(0),
                output_field=DecimalField(max_digits=15, decimal_places=6),
            )
        )
    
    def annotate_batch_values(self):
        """
        Annotate the queryset with the total value of each batch.

        This function adds an annotation to the queryset:
        - batch_value: The total value of each batch, calculated as quantity_remaining * effective_unit_cost.

        The annotation is calculated using an ExpressionWrapper that multiplies the quantity_remaining
        and effective_unit_cost fields of each batch object. The result is a DecimalField with a
        precision of up to 15 digits and 2 decimal places.
        """
        return self.annotate(
            batch_value=ExpressionWrapper(
                F('quantity_remaining') * F('effective_unit_cost'),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )
    
    def filter_empty_batches(self):
        """
        Filter the queryset to include only batches with a positive net quantity.

        This function first annotates the queryset with a `quantity_remaining` field,
        calculated as the difference between `total_in` and `total_out` quantities for
        each batch. It then filters the queryset to retain only those entries where
        `quantity_remaining` is greater than zero, effectively excluding empty or 
        depleted batches.
        """

        return self.annotate(
            quantity_remaining=F('total_in') - F('total_out')
        ).filter(quantity_remaining__gt=Decimal('0.0'))

class StockBatch(models.Model):
    date_received = models.DateTimeField(default=timezone.now)

    # GenericForeignKey fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_object = GenericForeignKey('content_type', 'object_id')

    objects = StockBatchQuerySet.as_manager()

    class Meta:
        ordering = ['date_received', 'id']
        verbose_name_plural = 'Stock Batches'

    def __str__(self):
        return f"{self.date_received.date()} - {self.linked_object.product.name} - {self.linked_object.quantity} {self.linked_object.product.unit}"
    
    @property
    def product(self):
        return self.linked_object.product

    @property
    def quantity(self):
        return self.linked_object.quantity
    
    @property
    def unit_cost(self):
        return self.linked_object.unit_cost
    
    @property
    def quantity_remaining(self):
        return self.get_quantity_remaining()
    
    @property
    def quantity_remaining_cost(self):
        return self.quantity_remaining * self.unit_cost
    
    @property
    def is_empty(self):
        return self.quantity_remaining <= 0
    
    @property
    def profit(self):
        """
        Calculate profit using database-level aggregation:
        profit = sum(quantity * (selling_price - unit_cost)) for all movements
        This is equivalent to:
        profit = sum(quantity * selling_price) - unit_cost * sum(quantity)
        """
        from inventory.models import BatchMovement, SaleItem
        movements = self.movements.filter(movement_type=BatchMovement.MovementType.OUT)

        movements = movements.annotate(
            sale_price=Subquery(
                SaleItem.objects
                .filter(pk=OuterRef('object_id'))
                .values('unit_price')[:1]
            )
        )

        revenue_aggregation = (
            movements
            .filter(
                content_type=ContentType.objects.get_for_model(SaleItem)
            )  
            .annotate(
                total_revenue=ExpressionWrapper(
                    F('quantity') * F('sale_price'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )
            .aggregate(revenue=Sum('total_revenue'))
        )['revenue'] or 0

        quantity_aggregation = (
            movements.filter(
                content_type=ContentType.objects.get_for_model(SaleItem)
            )
            .aggregate(total_quantity=Sum('quantity'))['total_quantity']
            or 0
        )

        unit_cost = self.linked_object.unit_cost
        return revenue_aggregation - (unit_cost * Decimal(quantity_aggregation))  
    
    def consume(self, quantity, associated_item):
        from inventory.models import BatchMovement
        ear_marked = min(quantity, self.quantity_remaining)
        ct = ContentType.objects.get_for_model(type(associated_item))
        
        if self.quantity_remaining > 0 and ear_marked > 0:
            self.movements.create(
                batch=self, 
                content_type=ct,
                object_id=associated_item.id if associated_item else None,
                quantity=ear_marked, 
                date=associated_item.date or timezone.now(),
                movement_type=BatchMovement.MovementType.OUT,
            )
        return quantity - ear_marked

    def get_quantity_remaining(self, date=None):
        from inventory.models import BatchMovement
        # Sum all 'IN' movements prior to or at `date`

        if not date:
            date = timezone.now()
            
        total_in = self.movements.filter(
            date__lt=date,
            movement_type=BatchMovement.MovementType.IN
        ).aggregate(
            total=Coalesce(Sum('quantity'), Decimal(0.0))
        )['total']

        # Sum all 'OUT' movements prior to or at `date`
        total_out = self.movements.filter(
            date__lt=date,
            movement_type=BatchMovement.MovementType.OUT
        ).aggregate(
            total=Coalesce(Sum('quantity'), Decimal(0.0))
        )['total']

        return total_in - total_out
