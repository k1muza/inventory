import csv
from decimal import Decimal
from io import StringIO
import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from .models import Product, Purchase, Sale, StockMovement
from .forms import PurchasesForm, SalesForm, StockAdjustmentForm

@transaction.atomic
def stock_new(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            stock_data = form.cleaned_data['stock_data']
            stock_date = form.cleaned_data['date']
            create_missing_products = form.cleaned_data['create_missing_products']
            adjustments = []
            errors = []

            f = StringIO(stock_data)
            reader = csv.reader(f, delimiter=',', skipinitialspace=True)

            purchase, _ = Purchase.objects.get_or_create(date=stock_date, is_initial_stock=True)

            for line in reader:
                # Parse each line
                product_name = line[0].strip()
                purchase_price = float(line[1].strip())
                selling_price = float(line[2].strip())
                quantity = float(line[3].strip())
                unit = line[4].strip()

                # Match product name
                try:
                    product = Product.objects.get(name__iexact=product_name)
                except Product.DoesNotExist:
                    if create_missing_products:
                        product = Product.objects.create(
                            name=product_name, 
                            purchase_price=purchase_price,
                            selling_price=selling_price,
                            unit=unit
                        )
                    else:
                        errors.append(f"Product '{product_name}' not found.")
                        continue

                adjustment = StockMovement(
                    product=product,
                    date=stock_date,
                    quantity=quantity,
                    movement_type='IN',
                    adjustment=True
                )
                adjustments.append(adjustment)

                purchase.items.create(product=product, quantity=quantity, unit_cost=purchase_price)

            # Save adjustments
            for adjustment in adjustments:
                adjustment.save()

            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Stock adjustments created successfully.")

            return redirect('inventory:stock_new')
    else:
        form = StockAdjustmentForm()

    return render(request, 'inventory/stock_form.html', {'form': form})


@transaction.atomic
def sales_form(request):
    if request.method == 'POST':
        form = SalesForm(request.POST)
        if form.is_valid():
            sales_data = form.cleaned_data['sales_data']
            sales_date = form.cleaned_data['date']
            errors = []

            f = StringIO(sales_data)
            reader = csv.reader(f, delimiter=',', skipinitialspace=True)

            sale, _ = Sale.objects.get_or_create(date=sales_date)

            for line in reader:
                # e.g. line[0] might be "Beef (5.50)", line[1] might be "4.365"
                raw_product_name = line[0].strip()

                # 1. Extract selling_price from parentheses, e.g. (5.50)
                match = re.search(r'\((.*?)\)', raw_product_name)
                if match:
                    # Convert bracketed text to float
                    selling_price = float(match.group(1))
                else:
                    # If there's no bracket, set a default or handle error
                    selling_price = 0.0

                # 2. Remove the (price) part from the product name
                product_name = re.sub(r'\(.*?\)', '', raw_product_name).strip()

                # 3. Parse quantity from second column
                # e.g. "4.365" or "11.295"
                quantity_str = line[1].strip()
                try:
                    quantity = Decimal(quantity_str)
                except ValueError:
                    errors.append(f"Invalid quantity '{quantity_str}' for line: {line}")
                    continue

                try:
                    product = Product.objects.get(name__iexact=product_name)
                except Product.DoesNotExist:
                    errors.append(f"Product '{product_name}' not found.")
                    continue
                
                sale.items.create(
                    product=product,
                    quantity=quantity,
                    unit_price=selling_price  # bracketed price
                )

            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Sales recorded successfully.")

            return redirect('inventory:sales_form')
    
    form = SalesForm()
    return render(request, 'inventory/sale_form.html', {'form': form})


@transaction.atomic
def purchases_form(request):
    if request.method == 'POST':
        form = PurchasesForm(request.POST)
        if form.is_valid():
            purchases_data = form.cleaned_data['purchases_data']
            purchases_date = form.cleaned_data['date']
            create_missing_products = form.cleaned_data['create_missing_products']
            errors = []

            f = StringIO(purchases_data)
            reader = csv.reader(f, delimiter=',', skipinitialspace=True)
            purchase, _ = Purchase.objects.get_or_create(date=purchases_date)

            for line in reader:
                product_name = line[0].strip()
                quantity_str = line[1].strip()
                match = re.match(r'(\d+(\.\d+)?)', quantity_str)
                if match:
                    quantity = Decimal(match.group(1))
                else:
                    messages.error(request, f"Invalid quantity: {quantity_str}")
                    raise ValueError(f"Bad quantity format: {quantity_str}")
                
                purchase_price = Decimal(line[2].replace('$', '').strip())

                try:
                    product = Product.objects.get(name__iexact=product_name)
                except Product.DoesNotExist:
                    if create_missing_products:
                        product = Product.objects.create(
                            name=product_name, 
                            purchase_price=purchase_price,
                            selling_price=0,
                            unit='unit'
                        )
                    else:
                        errors.append(f"Product '{product_name}' not found.")
                        continue
                
                unit_cost = purchase_price / quantity
                purchase.items.create(product=product, quantity=quantity, unit_cost=unit_cost)
                
            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Purchases recorded successfully.")

            return redirect('inventory:purchases_form')
        
    form = PurchasesForm()
    return render(request, 'inventory/purchase_form.html', {'form': form})
