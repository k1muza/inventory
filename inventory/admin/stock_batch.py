from django.contrib import admin

from inventory.models import BatchMovement, StockBatch


class BatchMovementInline(admin.TabularInline):
    model = BatchMovement
    extra = 0
    fields = ('date', 'quantity')
    can_delete = False
    ordering = ('date',)


@admin.register(StockBatch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        'date', 
        'product__name', 
        'quantity', 
        'quantity_remaining', 
        'unit_cost',
        'movements',
        'in_stock',
    )
    list_filter = ('date_received',)
    search_fields = ('product__name',)
    inlines = [BatchMovementInline]
    readonly_fields = ('quantity_remaining', 'is_empty', 'unit_cost',)
    ordering = ('-date_received',)

    @admin.display(description='Product')
    def product__name(self, obj: StockBatch):
        return obj.linked_object.product.name

    @admin.display(description='Date Received')
    def date(self, obj: StockBatch):
        return obj.date_received.date()

    @admin.display(description='Quantity Received')
    def quantity(self, obj: StockBatch):
        return f"{obj.linked_object.quantity:.2f} {obj.linked_object.product.unit}"

    @admin.display(description='Quantity Remaining')
    def quantity_remaining(self, obj: StockBatch):
        return f"{obj.quantity_remaining:.2f} {obj.linked_object.product.unit}"
    
    @admin.display(description='In Stock', boolean=True)
    def in_stock(self, obj: StockBatch):
        return not obj.is_empty
    
    @admin.display(description='Movements')
    def movements(self, obj: StockBatch):
        return obj.movements.filter(
            movement_type=BatchMovement.MovementType.OUT
        ).count()
    
    @admin.display(description='Unit Cost')
    def unit_cost(self, obj: StockBatch):
        return f"${obj.linked_object.unit_cost:.2f}"
