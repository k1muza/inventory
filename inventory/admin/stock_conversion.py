from django.contrib import admin

from inventory.models import StockConversion


@admin.register(StockConversion)
class StockConversionAdmin(admin.ModelAdmin):
    list_display = ('date', 'from_product', 'to_product', 'quantity', 'unit_cost')
    list_filter = ('date',)
    search_fields = ('from_product__name', 'to_product__name')
    ordering = ('-date',)

    fieldsets = (
        (None, {
            'fields': ('date',)
        }),
        ('Products', {
            'fields': ('from_product', 'to_product')
        }),
        ('Quantities', {
            'fields': ('quantity', 'unit_cost')
        }),
    )
