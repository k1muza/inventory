# Generated by Django 5.1.3 on 2024-12-03 23:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_remove_purchase_total_amount_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='quantity',
            field=models.FloatField(),
        ),
    ]
