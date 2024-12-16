from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('products/', views.product_list, name='product_list'),
    path('purchases-new/', views.purchases_new, name='purchases_new'),
    path('sales-new/', views.sales_new, name='sales_new'),
    path('stock-new/', views.stock_new, name='stock_new'),
]
