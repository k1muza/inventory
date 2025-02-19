from django.contrib import admin

from inventory.models import StockAdjustment


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('date', 'product', 'quantity', 'unit_cost')
    list_filter = ('date',)
    search_fields = ('product__name',)
    ordering = ('-date',)

    fieldsets = (
        (None, {
            'fields': ('date',)
        }),
        ('Product', {
            'fields': ('product',)
        }),
        ('Adjustment', {
            'fields': ('quantity', 'unit_cost')
        }),
    )
