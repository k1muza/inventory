from django.utils import timezone
from django import forms

class StockAdjustmentForm(forms.Form):
    stock_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 15,
            'class': 'form-control',
            'placeholder': 'Product Name, Quantity, Unit'
        }),
        label='Stock Take Data',
        help_text='Enter product data in the format: Product Name, Quantity, Unit'
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Stock Take Date',
        initial=forms.DateInput().format_value(timezone.now().strftime('%Y-%m-%d'))
    )
    create_missing_products = forms.BooleanField(
        initial=True,
        required=False,
        label='Create Missing Products',
        help_text='Create products that do not exist in the database.'
    )


class SalesForm(forms.Form):
    sales_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 15,
            'class': 'form-control',
            'placeholder': 'Product Name, Quantity, Unit'
        }),
        label='Sales Data',
        help_text='Enter sales data in the format: Product Name, Quantity, Unit'
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Sales Date',
        initial=forms.DateInput().format_value(timezone.now().strftime('%Y-%m-%d'))
    )


class PurchasesForm(forms.Form):
    purchases_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 15,
            'class': 'form-control',
            'placeholder': 'Product Name, Quantity, Unit'
        }),
        label='Purchases Data',
        help_text='Enter purchases data in the format: Product Name, Quantity, Unit'
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Purchases Date',
        initial=forms.DateInput().format_value(timezone.now().strftime('%Y-%m-%d'))
    )
    create_missing_products = forms.BooleanField(
        initial=True,
        required=False,
        label='Create Missing Products',
        help_text='Create products that do not exist in the database.'
    )
