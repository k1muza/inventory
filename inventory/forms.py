import csv
from decimal import Decimal
import decimal
from io import StringIO
import re
from django.utils import timezone
from django import forms
from django.core.exceptions import ValidationError

from inventory.models import Product


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

    def clean_sales_data(self):
        data = self.cleaned_data.get('sales_data')
        f = StringIO(data)
        reader = csv.reader(f, delimiter=",", skipinitialspace=True)
        parsed_sales = []
        errors = []
        for line_number, line in enumerate(reader, start=1):
            if not len(line):
                continue

            # e.g. "Beef (5.50)"
            try:
                raw_product_name = line[0].strip()
            except IndexError:
                errors.append(f'Badly formatted line: {line}')

            # Extract selling price in parentheses, if present.
            match = re.search(r'\((.*?)\)', raw_product_name)
            if match:
                try:
                    selling_price = Decimal(match.group(1))
                except Exception:
                    errors.append(f"Line {line_number}: Invalid selling price format in '{raw_product_name}'.")
                    continue
            else:
                selling_price = Decimal(0.0)

            # Remove the (price) part from the product name.
            product_name = re.sub(r'\(.*?\)', '', raw_product_name).strip()

            # Parse quantity from the second column.
            try:
                quantity_str = line[1].strip()
            except IndexError:
                errors.append(f"Line {line_number}: Badly formatted line: {line}")
                continue

            try:
                quantity = Decimal(quantity_str)
            except ValueError:
                errors.append(f"Line {line_number}: Invalid quantity '{quantity_str}' for line: {line}")
                continue
            except decimal.InvalidOperation:
                errors.append(f"Line {line_number}: Invalid quantity '{quantity_str}' for line: {line}")
                continue

            try:
                Product.objects.get(name__iexact=product_name)
            except Product.DoesNotExist:
                errors.append(f"Product '{product_name}' not found.")
                continue

            parsed_sales.append({
                'product_name': product_name,
                'selling_price': selling_price,
                'quantity': quantity,
            })

        if errors:
            raise ValidationError(errors)

        # Store the parsed data in cleaned_data for use in the view.
        self.cleaned_data['parsed_sales'] = parsed_sales
        return data

    def clean(self):
        cleaned_data = super().clean()
        # You could add additional cross-field validation here if needed.
        return cleaned_data


class PurchasesForm(forms.Form):
    purchases_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 15,
            'class': 'form-control',
            'placeholder': 'Product Name, Quantity, Price'
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

    def clean_purchases_data(self):
        """
        Validate and parse the CSV data.
        The parsed data will be stored in `self.cleaned_data['parsed_purchases']`.
        """
        data = self.cleaned_data.get('purchases_data')
        f = StringIO(data)
        reader = csv.reader(f, delimiter=",", skipinitialspace=True)
        parsed_purchases = []
        errors = []
        for line_number, line in enumerate(reader, start=1):
            if len(line) < 3:
                errors.append(f"Line {line_number}: Not enough columns.")
                continue

            product_name = line[0].strip()
            quantity_str = line[1].strip()
            price_str = line[2].strip()

            match = re.match(r"(\d+(\.\d+)?)", quantity_str)
            if not match:
                errors.append(f"Line {line_number}: Invalid quantity: {quantity_str}")
                continue

            try:
                quantity = Decimal(match.group(1))
            except Exception:
                errors.append(f"Line {line_number}: Cannot convert quantity: {quantity_str}")
                continue

            try:
                # Remove any '$' sign and whitespace before conversion.
                price = Decimal(price_str.replace("$", "").strip())
            except IndexError:
                errors.append(f"Line {line_number}: Invalid price: {price_str}")
                continue
            except decimal.InvalidOperation:
                errors.append(f"Line {line_number}: Invalid price: {price_str}")
                continue

            parsed_purchases.append({
                'product_name': product_name,
                'quantity': quantity,
                'price': price,
            })

        if errors:
            raise ValidationError(errors)

        # Store the parsed data in the cleaned_data so that the view can use it directly.
        self.cleaned_data['parsed_purchases'] = parsed_purchases
        return data

    def clean(self):
        """
        Optionally, add form-wide validation.
        For example, you could verify that products exist in the database if
        `create_missing_products` is False.
        """
        cleaned_data = super().clean()
        parsed_purchases = cleaned_data.get('parsed_purchases', [])
        create_missing_products = cleaned_data.get('create_missing_products')

        # Example: Validate that products exist if creation is not allowed.
        # from your_app.models import Product  <-- ensure you import your Product model
        for purchase in parsed_purchases:
            product_name = purchase['product_name']
            try:
                # Replace this with your actual product lookup logic.
                Product.objects.get(name__iexact=product_name)
            except Product.DoesNotExist:
                if not create_missing_products:
                    raise ValidationError(f"Product '{product_name}' not found.")
        return cleaned_data
