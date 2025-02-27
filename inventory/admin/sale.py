from django.contrib import admin

from inventory.models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    fields = ('product', 'quantity', 'unit_price', 'line_total',)
    readonly_fields = ('line_total',)

    @admin.display(description='Line Total')
    def line_total(self, obj):
        return f"${obj.line_total:.2f}"


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'total_amount',
        'cost_of_goods_sold',
        'gross_profit',
        'gross_margin'
    )
    inlines = [SaleItemInline]
    list_filter = ('date',)
    search_fields = ('notes',)
    readonly_fields = ('total_amount', 'cost_of_goods_sold', 'gross_profit', 'gross_margin')
    ordering = ['-date']

    fieldsets = (
        (None, {
            'fields': ('date',)
        }),
        ('Totals', {
            'fields': (
                'total_amount',
                'cost_of_goods_sold',
                'gross_profit',
                'gross_margin',
            )
        }),
        ('More Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Total Amount')
    def total_amount(self, obj: Sale):
        return f"${obj.total_amount:.2f}"

    @admin.display(description='Cost of Goods Sold')
    def cost_of_goods_sold(self, obj):
        return f"${obj.cost_of_goods_sold:.2f}"

    @admin.display(description="Gross Profit")
    def gross_profit(self, obj):
        return f"${obj.gross_profit:.2f}"

    @admin.display(description="Gross Margin")
    def gross_margin(self, obj):
        return f"{obj.gross_margin:.2%}"
