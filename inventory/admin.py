from datetime import timedelta
from django.utils import timezone
from django.contrib import admin
from django.db.models import Sum
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.conf import settings
from weasyprint import HTML

from .models import Cutting, Expense, Lot, LotConsumption, Report, Supplier, Product, StockMovement, Purchase, PurchaseItem, Sale, SaleItem, Transaction


admin.site.register(Supplier)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('date', 'product', 'movement_type', 'quantity')
    list_filter = ('date', 'movement_type')
    search_fields = ('product__name',)
    ordering = ('-date',)

    @admin.display(description='Product')
    def product(self, obj):
        return obj.product


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'transaction_type', 'item', 'amount')
    list_filter = ('date', 'transaction_type')
    search_fields = ('content_type__model',)

    @admin.display(description='Item')
    def item(self, obj):
        return obj.item


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('movement_type', 'quantity', 'date', 'balance_after')
    fields = ('date', 'movement_type', 'quantity', 'balance_after')
    can_delete = False
    ordering = ('-date',)  # Ensures movements are in chronological order

    @admin.display(description='Balance After')
    def balance_after(self, obj):
        stock_in = obj.product.stock_movements.filter(
            movement_type='IN',
            date__lte=obj.date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        stock_out = obj.product.stock_movements.filter(
            movement_type='OUT',
            date__lte=obj.date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        return f"{(stock_in - stock_out):.2f} {obj.product.unit}"

    def has_add_permission(self, request, obj):
        return False  # Prevent adding new stock movements from the inline

    def has_change_permission(self, request, obj=None):
        return False  # Make the inline read-only

    def has_delete_permission(self, request, obj=None):
        return False  # Prevent deletion from the inline
    

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    change_form_template = "admin/product_change_form.html"
    change_list_template = "admin/product_change_list.html"

    list_display = (
        'name', 
        'purchase_price',
        'stock_level', 
        'stock_value',
        'days_to_sell_out',
        'average_consumption',
        'average_gross_profit',
    )
    readonly_fields = (
        'stock_level', 
        'stock_value', 
        'average_consumption', 
        'average_gross_profit',
        'is_below_minimum_stock'
    )
    list_filter = ('unit',)
    search_fields = ('name',)
    inlines = [StockMovementInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'unit', 'batch_size')
        }),
        ('Pricing', {
            'fields': ('purchase_price', 'selling_price')
        }),
        ('Stock Levels', {
            'fields': ('minimum_stock_level', 'average_consumption')
        }),
        ('More Information', {
            'classes': ('collapse',),
            'fields': ('description',)
        }),
    )
    actions = ['generate_suggested_budget']

    @admin.display(description="Stock Level")
    def stock_level(self, obj: Product):
        return f"{obj.stock_level:.2f} {obj.unit}"
    
    @admin.display(description="Stock Value")
    def stock_value(self, obj: Product):
        return f"${obj.stock_value:.2f}"

    @admin.display(description="Below Minimum Stock", boolean=True)
    def is_below_minimum_stock(self, obj: Product):
        return obj.is_below_minimum_stock()
    
    @admin.display(description="Av Consumption/Day")
    def average_consumption(self, obj: Product):
        return f"{obj.average_consumption:.2f} {obj.unit}"
    
    @admin.display(description="Av Profit/Day")
    def average_gross_profit(self, obj: Product):
        return f"${obj.average_gross_profit:.2f}"
    
    @admin.display(description="Days to Sell Out")
    def days_to_sell_out(self, obj: Product):
        return f"{obj.days_until_stockout:.2f} days"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/download-pdf/', self.admin_site.admin_view(self.download_pdf), name='product-download-pdf'),
            path('suggest-budget/', self.admin_site.admin_view(self.suggest_budget_view), name='product-suggest-budget'),
        ]
        return custom_urls + urls

    def download_pdf(self, request, object_id, *args, **kwargs):
        product = get_object_or_404(Product, pk=object_id)
        movements = product.stock_movements.all().order_by('date', 'movement_type')

        # Compute running balance
        running_balance = 0
        movements_with_balance = []
        for m in movements:
            if m.movement_type == 'IN':
                running_balance += m.quantity
            else:  # OUT movement
                running_balance -= m.quantity

            movements_with_balance.append({
                'date': m.date,
                'movement_type': m.get_movement_type_display(),
                'quantity': int(m.quantity) if product.unit == 'unit' else f"{m.quantity:.2f}",
                'reference': getattr(m, 'reference', ''),
                'running_balance': running_balance,
            })

        # Render the HTML template for the PDF
        html = render(request, 'admin/product_pdf.html', {
            'product': product,
            'movements': movements_with_balance
        }).content.decode('utf-8')

        # Generate PDF
        pdf = HTML(string=html).write_pdf()

        # Return PDF as a download
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"{product.name} Report.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def suggest_budget_view(self, request):
        products = Product.objects.all()
        suggested_purchases = []
        total_reorder_cost = 0
        for p in products:
            req = p.reorder_quantity
            if req > 0:
                suggested_purchases.append(p)
                total_reorder_cost += p.batch_sized_reorder_value

        # Render HTML template for PDF
        html_content = render(request, 'admin/product_suggested_budget.html', {
            'products': suggested_purchases,
            'total_reorder_cost': total_reorder_cost,
            'generated_at': timezone.now(),
            'reorder_interval': settings.REORDER_INTERVAL_DAYS,
        }).content.decode('utf-8')

        # Generate PDF using WeasyPrint
        pdf = HTML(string=html_content).write_pdf()

        # Return as PDF download
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = "suggested_budget.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


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
        'cost',
        'gross_profit', 
        'profit', 
        'gross_margin'
    )
    inlines = [SaleItemInline]
    list_filter = ('date',)
    search_fields = ('notes',)
    readonly_fields = ('total_amount', 'cost_of_goods_sold', 'gross_profit', 'profit', 'gross_margin')

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
    def total_amount(self, obj):
        return f"${obj.total_amount:.2f}"
    
    @admin.display(description='Cost of Goods Sold')
    def cost_of_goods_sold(self, obj):
        return f"${obj.cost_of_goods_sold:.2f}"
    
    @admin.display(description='Cost')
    def cost(self, obj: Sale):
        return f"${obj.cost:.2f}"
    
    @admin.display(description="Gross Profit")
    def gross_profit(self, obj):
        return f"${obj.gross_profit:.2f}"
    
    @admin.display(description="Profit")
    def profit(self, obj: Sale):
        return f"${obj.profit:.2f}"
    
    @admin.display(description="Gross Margin")
    def gross_margin(self, obj):
        return f"{obj.gross_margin:.2%}"


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'amount', 'date')
    list_filter = ('date',)
    search_fields = ('description',)
    ordering = ('-date',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('open_date', 'close_date', 'total_sales', 'total_expenses', 'net_profit')
    readonly_fields = (
        'total_sales', 
        'total_expenses', 
        'total_purchases',
        'gross_profit', 
        'net_profit', 
        'gross_margin',
        'net_margin',
        'opening_stock', 
        'closing_stock',
        'opening_cash',
        'closing_cash',

    )
    ordering = ('-open_date',)

    fieldsets = (
        ('Modify Period', {
            'classes': ('collapse',),
            'fields': ('open_date', 'close_date')
        }),
        ('Totals', {
            'fields': (
                'total_sales', 
                'total_purchases', 
                'total_expenses',)
        }),
        ('Profits', {
            'fields': (
                'gross_profit', 
                'net_profit',
                'gross_margin',
                'net_margin',
            )
        }),
        ('Stock Movements', {
            'fields': ('opening_stock', 'closing_stock')
        }),
        ('Cash Movements', {
            'fields': ('opening_cash', 'closing_cash')
        }),
    )

    @admin.display(description='Total Sales')
    def total_sales(self, obj):
        return f"${obj.total_sales:.2f}"
    
    @admin.display(description='Total Purchases')
    def total_purchases(self, obj):
        return f"${obj.total_purchases:.2f}"
    
    @admin.display(description='Gross Profit')
    def gross_profit(self, obj):
        return f"${obj.gross_profit:.2f}"
    
    @admin.display(description='Total Expenses')
    def total_expenses(self, obj):
        return f"${obj.total_expenses:.2f}"
    
    @admin.display(description='Net Profit')
    def net_profit(self, obj):
        return f"${obj.net_profit:.2f}"
    
    @admin.display(description='Gross Margin')
    def gross_margin(self, obj):
        return f"{obj.gross_margin:.2%}"
    
    @admin.display(description='Net Margin')
    def net_margin(self, obj):
        return f"{obj.net_margin:.2%}"
    
    @admin.display(description='Opening Stock')
    def opening_stock(self, obj):
        return f"${obj.opening_stock_value:.2f}"
    
    @admin.display(description='Closing Stock')
    def closing_stock(self, obj):
        return f"${obj.closing_stock_value:.2f}"
    
    @admin.display(description='Opening Cash')
    def opening_cash(self, obj):
        return f"${obj.opening_cash:.2f}"
    
    @admin.display(description='Closing Cash')
    def closing_cash(self, obj):
        return f"${obj.closing_cash:.2f}"


class LotConsumptionInline(admin.TabularInline):
    model = LotConsumption
    extra = 0
    fields = ('date_consumed', 'quantity')
    can_delete = False
    ordering = ('date_consumed',)


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = (
        'date_received', 
        'purchase_item__product__name', 
        'purchase_item__quantity', 
        'quantity_remaining', 
        'sales_count',
        'in_stock',
    )
    list_filter = ('date_received',)
    search_fields = ('purchase_item__product__name',)
    inlines = [LotConsumptionInline]
    readonly_fields = ('quantity_remaining', 'is_empty')
    ordering = ('-date_received',)

    @admin.display(description='Quantity Remaining')
    def quantity_remaining(self, obj: Lot):
        return f"{obj.quantity_remaining:.2f} {obj.purchase_item.product.unit}"
    
    @admin.display(description='In Stock', boolean=True)
    def in_stock(self, obj: Lot):
        return not obj.is_empty
    
    @admin.display(description='Sales Count')
    def sales_count(self, obj: Lot):
        return obj.consumptions.count()


@admin.register(Cutting)
class CuttingAdmin(admin.ModelAdmin):
    list_display = ('date', 'lot__purchase_item__product__name', 'quantity', 'unit_cost', 'total_cost')
    list_filter = ('date', 'lot__purchase_item__product__name')
    search_fields = ('lot__purchase_item__product__name',)
    ordering = ('-date',)

    @admin.display(description='Total Cost')
    def total_cost(self, obj: Cutting):
        return f"${obj.total_cost:.2f}"
