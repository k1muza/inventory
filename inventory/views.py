import csv
from io import StringIO
import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from .models import Cutting, Product, Purchase, Sale, StockMovement
from .forms import CuttingForm, PurchasesForm, SalesForm, StockAdjustmentForm

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
def sales_new(request):
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
                product_name = re.sub(r'\(.*?\)', '', line[0].strip()).strip()
                quantity = float(line[1].strip())

                try:
                    product = Product.objects.get(name__iexact=product_name)
                except Product.DoesNotExist:
                    errors.append(f"Product '{product_name}' not found.")
                    continue
                
                sale.items.create(product=product, quantity=quantity, unit_price=product.selling_price)

            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Sales recorded successfully.")

            return redirect('inventory:sales_new')
    
    form = SalesForm()
    return render(request, 'inventory/sale_form.html', {'form': form})


@transaction.atomic
def purchases_new(request):
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
                purchase_price = float(line[1].strip())
                quantity = float(line[2].strip())

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

                purchase.items.create(product=product, quantity=quantity, unit_cost=purchase_price)
                
            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Purchases recorded successfully.")

            return redirect('inventory:purchases_new')
        
    form = PurchasesForm()
    return render(request, 'inventory/purchase_form.html', {'form': form})


def cutting_new(request):
    if request.method == 'POST':
        form = CuttingForm(request.POST)
        if form.is_valid():
            # Extract cleaned data
            lot = form.cleaned_data['lot']
            quantity_reduction = form.cleaned_data['quantity_reduction']
            quantity = form.cleaned_data['quantity']
            unit_cost = form.cleaned_data['unit_cost']
            date = form.cleaned_data['date']

            # Create and save the Cutting instance
            Cutting.objects.create(
                lot=lot,
                quantity=quantity,
                quantity_reduction=quantity_reduction,
                unit_cost=unit_cost,
                date=date
            )

            messages.success(request, "Cutting record created successfully!")
            return redirect('cutting_list')  # Adjust redirect to an appropriate view
        else:
            # Form invalid, show errors
            messages.error(request, "Please correct the errors below.")
    else:
        form = CuttingForm()

    return render(request, 'inventory/cutting_form.html', {'form': form})
