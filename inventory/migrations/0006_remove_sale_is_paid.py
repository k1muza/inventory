# Generated by Django 5.1.3 on 2024-12-03 23:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_alter_stockmovement_quantity'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sale',
            name='is_paid',
        ),
    ]
