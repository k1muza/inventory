from django.contrib import admin
from django.db.models import Sum
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, HttpRequest
from django.utils import timezone
from django.conf import settings
from django.utils.safestring import mark_safe
from weasyprint import HTML

from inventory.models import StockMovement, Product


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('movement_type', 'type', 'quantity', 'date', 'balance_after', 'details')
    fields = ('date', 'movement_type', 'type', 'quantity', 'balance_after', 'details')
    can_delete = False
    ordering = ('-date',)  # Ensures movements are in chronological order

    @admin.display(description='Balance After')
    def balance_after(self, obj: StockMovement):
        stock_in = obj.product.stock_movements.filter(
            movement_type='IN',
            date__lte=obj.date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        stock_out = obj.product.stock_movements.filter(
            movement_type='OUT',
            date__lte=obj.date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        return f"{(stock_in - stock_out):.2f} {obj.product.unit}"
    
    @admin.display(description='Movement Type')
    def type(self, obj):
        return f"{obj.get_movement_type_display()} ({obj.linked_object.name})" if obj.linked_object else obj.get_movement_type_display()
    
    @admin.display(description='Details')
    def details(self, obj: StockMovement):
        return mark_safe(f'<a href="{obj.get_admin_url()}">View</a>')

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
        'unit_cost',
        'average_unit_cost',
        'stock_level', 
        'batch_level',
        'stock_value',
        'days_to_sell_out',
        'average_consumption',
        'average_gross_profit',
    )
    readonly_fields = (
        'stock_level', 
        'stock_value', 
        'batch_level',
        'average_consumption', 
        'average_gross_profit',
        'average_unit_cost',
        'is_below_minimum_stock',
    )
    list_filter = ('unit', 'is_active')
    search_fields = ('name',)
    inlines = [StockMovementInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'unit', 'batch_size', 'predict_demand', 'is_active')
        }),
        ('Pricing', {
            'fields': ('unit_cost', 'unit_price')
        }),
        ('Stock Levels', {
            'fields': ('minimum_stock_level', 'average_consumption')
        }),
        ('More Information', {
            'classes': ('collapse',),
            'fields': ('description',)
        }),
    )

    @admin.display(description="Stock Level")
    def stock_level(self, obj: Product):
        return f"{obj.stock_level:.3f} {obj.unit}"
    
    @admin.display(description="Batch Level")
    def batch_level(self, obj: Product):
        return f"{obj.batch_based_stock_level:.3f} {obj.unit}"
    
    @admin.display(description="Stock Value")
    def stock_value(self, obj: Product):
        return f"${obj.stock_value:.2f}"

    @admin.display(description="Below Minimum Stock", boolean=True)
    def is_below_minimum_stock(self, obj: Product):
        return obj.is_below_minimum_stock()
    
    @admin.display(description="Av Consumption/Day")
    def average_consumption(self, obj: Product):
        return f"{obj.average_consumption:.3f} {obj.unit}"
    
    @admin.display(description="Av Unit Cost")
    def average_unit_cost(self, obj: Product):
        return f"${obj.average_unit_cost:.2f}"
    
    @admin.display(description="Av Profit/Day")
    def average_gross_profit(self, obj: Product):
        return f"${obj.average_gross_profit:.2f}"
    
    @admin.display(description="Days to Sell Out")
    def days_to_sell_out(self, obj: Product):
        return f"{obj.days_until_stockout:.1f} days"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/sales-report/', self.admin_site.admin_view(self.sales_report), name='product-sales-report'),
            path('<int:object_id>/download-pdf/', self.admin_site.admin_view(self.download_pdf), name='product-download-pdf'),
            path('suggest-budget/', self.admin_site.admin_view(self.suggest_budget_view), name='product-suggest-budget'),
            path('sales-graph/', self.admin_site.admin_view(self.sales_graph), name='product-sales-graph'),
            path('sales-predictions/', self.admin_site.admin_view(self.sales_predictions), name='product-sales-predictions'),
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
                'movement_type': f"{m.get_movement_type_display()} ({m.linked_object.name})" if m.linked_object else m.get_movement_type_display(),
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

    def suggest_budget_view(self, request: HttpRequest, *args, **kwargs):
        products = Product.objects.filter(is_active=True)
        suggested_purchases = []
        total_reorder_cost = 0
        realizable_profit = 0
        for p in products:
            req = p.reorder_quantity
            if req > 0:
                suggested_purchases.append(p)
                total_reorder_cost += p.batch_sized_reorder_value
                # realizable_profit += p.batch_sized_reorder_quantity * p.latest_unit_profit

        # Render HTML template for PDF
        html_content = render(request, 'admin/product_suggested_budget.html', {
            'products': suggested_purchases,
            'total_reorder_cost': total_reorder_cost,
            'generated_at': timezone.now(),
            'reorder_interval': settings.REORDER_INTERVAL_DAYS,
            'realizable_profit': realizable_profit,
        }).content.decode('utf-8')

        # Generate PDF using WeasyPrint
        pdf = HTML(string=html_content).write_pdf()

        # Return as PDF download
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = "suggested_budget.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def sales_report(self, request, object_id, *args, **kwargs):
        product = get_object_or_404(Product, pk=object_id)
        sales = product.sale_items.all().order_by('sale__date').values(
            'sale__date',
            'quantity',
        )

        items = []
        for sale in sales:
            items.append({
                'date': sale['sale__date'].strftime('%Y-%m-%d'),
                'quantity': sale['quantity'],
            })

        context = {
            'product': product,
            'sales': items,
        }

        return render(request, 'admin/product_sales_report.html', context)
    
    def sales_graph(self, request):
        products = Product.objects.filter(unit='kg')
        line = []
        for p in products:
            line.append({
                'name': p.name,
                'sales': list(p.sale_items.all().order_by('sale__date').values(
                    'sale__date',
                    'quantity',
                ))
            })

        context = {
            'products': line,
        }

        return render(request, 'admin/product_sales_graph.html', context)
    
    def sales_predictions(self, request):
        from utils.predictor import Predictor
        predictor = Predictor()
        products = Product.objects.filter(predict_demand=True, is_active=True, unit='kg')
        line = []
        for p in products:
            forecasts = predictor.predict_sales(p)
            sales = []
            for forecast in forecasts:
                sales.append({
                    'date': forecast['ds'].strftime('%Y-%m-%d'),
                    'quantity': round(forecast['yhat'], 3),
                })

            line.append({
                'name': p.name,
                'sales': sales
            })

        context = {
            'products': line,
        }

        return render(request, 'admin/product_sales_predictions.html', context)
