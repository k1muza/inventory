# Generated by Django 5.1.3 on 2024-12-30 21:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0032_stockadjustment_stockconversion_delete_meatprocess'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Lot',
            new_name='StockBatch',
        ),
    ]
