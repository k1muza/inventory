# Inventory Management System

A Django-based inventory management solution designed to track products, sales, purchases, expenses, stock adjustments, and more. This project provides robust tools for managing inventory operations, detailed reporting, and seamless integration via a GraphQL API.

---

## Overview

The Inventory Management System is built using Django and is tailored for businesses needing to monitor and control their inventory. Key aspects include:

- **Product Management:** Manage products with details such as pricing, cost, supplier information, and stock levels.
- **Sales & Purchases:** Record and track sales and purchase transactions with associated line items.
- **Expense Tracking:** Log expenses with descriptions, categories, and amounts.
- **Stock Management:** Handle stock adjustments, batch movements, and stock conversions for precise inventory tracking.
- **Financial Reporting:** Generate reports that calculate total sales, gross profit, cost of goods sold, net profit, and margins.
- **GraphQL API:** Utilize a GraphQL endpoint built with Strawberry for advanced querying and integration.
- **Admin Interface:** Leverage Django’s built-in admin panel for comprehensive management of inventory data.

---

## Features

- **Products:** Define and manage product details including unit cost, pricing, supplier, minimum stock levels, and more.
- **Purchases & Purchase Items:** Record purchases with line items that detail quantities, unit costs, and associated stock batches.
- **Sales & Sale Items:** Process sales transactions while automatically calculating revenue, cost of goods sold, and profit.
- **Expenses:** Track operational expenses with detailed categorization.
- **Stock Adjustments & Conversions:** Adjust inventory counts and convert stock between products while maintaining accurate records.
- **Batch & Stock Movements:** Monitor inventory changes with batch movements and individual stock movement records.
- **Financial Reports:** Calculate key metrics such as opening/closing stock value, gross profit, net profit, and margins over specified reporting periods.
- **GraphQL Integration:** Access and manipulate inventory data using a GraphQL API.

---

## Requirements

- **Python:** 3.8 or higher
- **Django:** 5.1.3 or compatible version
- **Database:** PostgreSQL (or any other database supported by Django)
- **Additional Packages:**  
  - `strawberry`
  - `strawberry-django`
  - `django-environ`

---

## Installation & Setup

1. **Clone the Repository:**

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a Virtual Environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
Create a .env file in the project root and add:

   ```bash
   SECRET_KEY=your-secret-key
   DEBUG=True
   ALLOWED_HOSTS=127.0.0.1,localhost
   DATABASE_URL=sqlite:///db.sqlite3 # or 'postgres://user:pass@localhost/db'
   ```

5. **Run Migrations:**

   ```bash
   python manage.py migrate
   ```

6. **Start the Development Server:**

   ```bash
   python manage.py runserver
   ```

7. **Access the Admin Interface:**

   Open http://localhost:8000/admin to access the Django admin interface.   

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgments

- [Django](https://www.djangoproject.com/)
- [Strawberry GraphQL](https://strawberry.rocks/)
- [Factory Boy](https://factoryboy.readthedocs.io/en/latest/index.html)
