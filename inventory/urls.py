from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('cutting-form/', views.cutting_new, name='cutting_form'),
    path('purchases-form/', views.purchases_new, name='purchases_form'),
    path('sales-form/', views.sales_new, name='sales_form'),
    path('stock-form/', views.stock_new, name='stock_form'),
]
