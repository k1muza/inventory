from django.contrib import admin

from inventory.models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_email', 'contact_phone', 'address')
    search_fields = ('name', 'contact_email', 'contact_phone', 'address')
