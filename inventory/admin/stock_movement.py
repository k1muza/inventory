from django.contrib import admin

from inventory.models.stock_movement import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('date', 'product', 'movement_type', 'quantity')
    list_filter = ('date', 'movement_type')
    search_fields = ('product__name',)
    ordering = ('-date',)

    @admin.display(description='Product')
    def product(self, obj):
        return obj.product
