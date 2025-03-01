from django.contrib import admin
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.http import HttpResponse
from weasyprint import HTML

from inventory.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    change_form_template = "admin/report_change_form.html"

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
    def opening_stock(self, obj: Report):
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<str:object_id>/income-statement/',
                self.admin_site.admin_view(self.download_income_statement),
                name='income-statement',
            ),
            path(
                '<str:object_id>/movement-report/',
                self.admin_site.admin_view(self.movement_report),
                name='movement-report',
            ),
            path(
                '<str:object_id>/profitability-report/',
                self.admin_site.admin_view(self.profitability_report),
                name='profitability-report',
            )
        ]
        return custom_urls + urls

    def download_income_statement(self, request, object_id, *args, **kwargs):
        report = get_object_or_404(Report, pk=object_id)
        # Render HTML template
        html_content = render(
            request,
            "admin/income_statement.html",
            {"report": report, "generated_at": timezone.now()},
        ).content.decode("utf-8")

        # Convert to PDF
        pdf = HTML(string=html_content).write_pdf()

        # Return PDF as response
        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"""{report.open_date.strftime('%Y-%m-%d')} - {report.close_date.strftime('%Y-%m-%d')} Income Statement: Generated ({timezone.now().strftime('%Y-%m-%d %H:%M:%S')}).pdf"""
        response["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    def open_balance_sheet(self, request, object_id, *args, **kwargs):
        report = get_object_or_404(Report, pk=object_id)
        # Render HTML template
        html_content = render(
            request,
            "admin/balance_sheet.html",
            {"report": report, "balance_type": "Opening"}
        ).content.decode("utf-8")

        # Convert to PDF
        pdf = HTML(string=html_content).write_pdf()

        # Return PDF as response
        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"opening_balance_sheet_{report.id}.pdf"
        response["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    def movement_report(self, request, object_id, *args, **kwargs):
        report = get_object_or_404(Report, pk=object_id)
        # Render HTML template
        html_content = render(
            request,
            "admin/movements_report.html",
            {
                "report": report,
                "generated_at": timezone.now(),
            }
        ).content.decode("utf-8")

        # Convert to PDF
        pdf = HTML(string=html_content).write_pdf()

        # Return PDF as response
        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"inventory_movements_{report.id}.pdf"
        response["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    def profitability_report(self, request, object_id, *args, **kwargs):
        report = get_object_or_404(Report, pk=object_id)
        # Render HTML template
        html_content = render(
            request,
            "admin/profitability_report.html",
            {
                "report": report,
                "generated_at": timezone.now(),
                "total": sum(i['gross_profit'] for i in report.product_performances)
            }
        ).content.decode("utf-8")

        # Convert to PDF
        pdf = HTML(string=html_content).write_pdf()

        # Return PDF as response
        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"Inventory and Profitability Report {report.id}.pdf"
        response["Content-Disposition"] = f"attachment; filename={filename}"
        return response
