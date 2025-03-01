import csv
from decimal import Decimal
import decimal
from io import StringIO
import re
from datetime import datetime
from typing import List
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpRequest

from .models import Product, Purchase, Sale, StockMovement
from .forms import PurchasesForm, SalesForm, StockAdjustmentForm


@transaction.atomic
def stock_new(request: HttpRequest) -> HttpResponse:
    """
    Form for recording stock adjustments.

    Handles POST requests with form data and redirects to the same page.

    :param request: The request object.
    :return: The rendered form page as an HTTP response.
    """
    if request.method == "POST":
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            stock_data = form.cleaned_data["stock_data"]
            stock_date: datetime = form.cleaned_data["date"]
            create_missing_products: bool = form.cleaned_data["create_missing_products"]
            adjustments: List[StockMovement] = []
            errors: List[str] = []

            f = StringIO(stock_data)
            reader = csv.reader(f, delimiter=",", skipinitialspace=True)

            purchase, _ = Purchase.objects.get_or_create(
                date=stock_date, is_initial_stock=True
            )

            for line in reader:
                # Parse each line
                product_name = line[0].strip()
                purchase_price: float = float(line[1].strip())
                selling_price: float = float(line[2].strip())
                quantity: float = float(line[3].strip())
                unit: str = line[4].strip()

                # Match product name
                try:
                    product = Product.objects.get(name__iexact=product_name)
                except Product.DoesNotExist:
                    if create_missing_products:
                        product = Product.objects.create(
                            name=product_name,
                            unit_cost=purchase_price,
                            unit_price=selling_price,
                            unit=unit,
                        )
                    else:
                        errors.append(f"Product '{product_name}' not found.")
                        continue

                adjustment = StockMovement(
                    product=product,
                    date=stock_date,
                    quantity=quantity,
                    movement_type="IN",
                    adjustment=True,
                )
                adjustments.append(adjustment)

                purchase.items.create(
                    product=product, quantity=quantity, unit_cost=purchase_price
                )

            # Save adjustments
            for adjustment in adjustments:
                adjustment.save()

            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Stock adjustments created successfully.")

            return redirect("inventory:stock_new")
    else:
        form = StockAdjustmentForm()

    return render(request, "inventory/stock_form.html", {"form": form})


@transaction.atomic
def sales_form(request: HttpRequest) -> HttpResponse:
    """
    Form for recording sales.

    Handles POST requests with form data and redirects to the same page.

    :param request: The request object.
    :return: The rendered page.
    """
    if request.method == "POST":
        form = SalesForm(request.POST)
        if form.is_valid():
            sales_data: str = form.cleaned_data["sales_data"]
            sales_date: datetime.date = form.cleaned_data["date"]
            errors: List[str] = []

            f = StringIO(sales_data)
            reader = csv.reader(f, delimiter=",", skipinitialspace=True)

            sale, _ = Sale.objects.get_or_create(date=sales_date)

            for line in reader:
                # e.g. line[0] might be "Beef (5.50)", line[1] might be "4.365"
                raw_product_name: str = line[0].strip()

                # 1. Extract selling_price from parentheses, e.g. (5.50)
                match = re.search(r'\((.*?)\)', raw_product_name)
                if match:
                    # Convert bracketed text to float
                    selling_price: Decimal = Decimal(match.group(1))
                else:
                    # If there's no bracket, set a default or handle error
                    selling_price = Decimal(0.0)

                # 2. Remove the (price) part from the product name
                product_name: str = re.sub(r'\(.*?\)', '', raw_product_name).strip()

                # 3. Parse quantity from second column
                # e.g. "4.365" or "11.295"
                quantity_str: str = line[1].strip()
                try:
                    quantity: Decimal = Decimal(quantity_str)
                except ValueError:
                    errors.append(f"Invalid quantity '{quantity_str}' for line: {line}")
                    raise ValueError(f"Bad quantity format: {quantity_str}")
                except decimal.InvalidOperation:
                    errors.append(f"Invalid quantity '{quantity_str}' for line: {line}")
                    raise ValueError(f"Bad quantity format: {quantity_str}")

                try:
                    product: Product = Product.objects.get(name__iexact=product_name)
                except Product.DoesNotExist:
                    errors.append(f"Product '{product_name}' not found.")
                    continue

                sale.items.create(
                    product=product,
                    quantity=quantity,
                    unit_price=selling_price,  # bracketed price
                )

            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Sales recorded successfully.")

            return redirect("inventory:sales_form")

    form = SalesForm()
    return render(request, "inventory/sale_form.html", {"form": form})


@transaction.atomic
def purchases_form(request: HttpRequest) -> HttpResponse:
    """
    Form for recording purchases.

    Handles POST requests with form data and redirects to the same page.

    :param request: The request object.
    :return: The rendered form page.
    """
    if request.method == "POST":
        form = PurchasesForm(request.POST)
        if form.is_valid():
            purchases_data = form.cleaned_data["purchases_data"]
            purchases_date: datetime = form.cleaned_data["date"]
            create_missing_products: bool = form.cleaned_data["create_missing_products"]
            errors: list[str] = []

            f = StringIO(purchases_data)
            reader = csv.reader(f, delimiter=",", skipinitialspace=True)
            purchase, _ = Purchase.objects.get_or_create(date=purchases_date)

            for line in reader:
                product_name = line[0].strip()
                quantity_str = line[1].strip()
                match = re.match(r"(\d+(\.\d+)?)", quantity_str)
                if match:
                    quantity: Decimal = Decimal(match.group(1))
                else:
                    messages.error(request, f"Invalid quantity: {quantity_str}")
                    raise ValueError(f"Bad quantity format: {quantity_str}")

                purchase_price: Decimal = Decimal(line[2].replace("$", "").strip())

                try:
                    product = Product.objects.get(name__iexact=product_name)
                except Product.DoesNotExist:
                    if create_missing_products:
                        product = Product.objects.create(
                            name=product_name,
                            unit_cost=purchase_price,
                            unit_price=None,
                            unit="unit",
                        )
                    else:
                        errors.append(f"Product '{product_name}' not found.")
                        continue

                unit_cost = purchase_price / quantity
                purchase.items.create(
                    product=product, quantity=quantity, unit_cost=unit_cost
                )

            if errors:
                messages.error(request, "Some errors occurred during processing:")
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "Purchases recorded successfully.")

            return redirect("inventory:purchases_form")

    form = PurchasesForm()
    return render(request, "inventory/purchase_form.html", {"form": form})
