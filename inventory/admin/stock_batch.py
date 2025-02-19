from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect

from inventory.models import BatchMovement, StockBatch, PurchaseItem, StockAdjustment, StockConversion, SaleItem


class BatchMovementInline(admin.TabularInline):
    model = BatchMovement
    extra = 0
    fields = ('date', 'quantity')
    can_delete = False
    ordering = ('date',)


@admin.register(StockBatch)
class BatchAdmin(admin.ModelAdmin):
    change_list_template = 'admin/stock_batch_change_list.html'
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
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('batches-recalculate/', self.admin_site.admin_view(self.recalculate_batches), name='batches-recalculate'),
        ]
        return my_urls + urls
    
    def recalculate_batches(self, request):
        StockBatch.objects.all().delete()

        for item in PurchaseItem.objects.all():
            item.save()

        for item in StockAdjustment.objects.all():
            item.save()

        for item in StockConversion.objects.all():
            item.save()

        for item in SaleItem.objects.all():
            item.save()

        self.message_user(request, 'Batches Recalculated')

        # Redirect to batches list
        return HttpResponseRedirect(request.path)
