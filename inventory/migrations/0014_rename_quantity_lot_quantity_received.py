# Generated by Django 5.1.3 on 2024-12-18 05:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0013_product_batch_size'),
    ]

    operations = [
        migrations.RenameField(
            model_name='lot',
            old_name='quantity',
            new_name='quantity_received',
        ),
    ]
