from django.contrib import admin

from inventory.models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_date', 'description', 'amount',)
    list_filter = ('date', 'description',)
    search_fields = ('description',)
    ordering = ('-date',)

    @admin.display(description='Date')
    def expense_date(self, obj: Expense):
        return obj.date.strftime('%Y-%m-%d')
