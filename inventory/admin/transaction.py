from django.contrib import admin
from inventory.models.transaction import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'transaction_type', 'item', 'amount')
    list_filter = ('date', 'transaction_type')
    search_fields = ('content_type__model',)

    @admin.display(description='Item')
    def item(self, obj):
        return obj.item
