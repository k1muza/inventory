# Generated by Django 5.1.3 on 2024-12-18 15:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0018_rename_cost_per_unit_purchaseitem_unit_cost'),
    ]

    operations = [
        migrations.RenameField(
            model_name='lot',
            old_name='cost_per_unit',
            new_name='unit_cost',
        ),
        migrations.RemoveField(
            model_name='lotconsumption',
            name='selling_price',
        ),
        migrations.AddField(
            model_name='lotconsumption',
            name='description',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='lotconsumption',
            name='sale_item',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='inventory.saleitem'),
        ),
    ]
