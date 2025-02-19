from django.contrib import admin

from inventory.models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    fields = ('product', 'quantity', 'unit_cost', 'line_total',)
    readonly_fields = ('line_total',)

    @admin.display(description='Line Total')
    def line_total(self, obj):
        return f"${obj.line_total:.2f}"


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_amount')
    inlines = [PurchaseItemInline]
    list_filter = ('date',)
    search_fields = ('notes',)
    readonly_fields = ('total_amount',)
    ordering = ('-date',)

    fieldsets = (
        (None, {
            'fields': ('date',)
        }),
        ('Totals', {
            'fields': ('total_amount',)
        }),
        ('More Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Total Amount')
    def total_amount(self, obj):
        return f"${obj.total_amount:.2f}"
