# Generated by Django 5.1.3 on 2024-12-21 05:22

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0025_rename_quantity_reduction_cutting_ending_weight_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MeatProcessing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('process_type', models.CharField(choices=[('CUTTING', 'Cutting'), ('SLICING', 'Slicing'), ('MINCING', 'Mincing'), ('PACKAGING', 'Packaging')], max_length=20)),
                ('starting_weight', models.DecimalField(decimal_places=3, max_digits=10)),
                ('ending_weight', models.DecimalField(decimal_places=3, max_digits=10)),
                ('unit_cost', models.DecimalField(decimal_places=2, max_digits=15)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.lot')),
            ],
        ),
    ]
