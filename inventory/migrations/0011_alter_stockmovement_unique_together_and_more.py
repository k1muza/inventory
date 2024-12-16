# Generated by Django 5.1.3 on 2024-12-11 20:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('inventory', '0010_remove_purchase_is_paid'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='stockmovement',
            unique_together={('content_type', 'object_id')},
        ),
        migrations.AlterUniqueTogether(
            name='transaction',
            unique_together={('content_type', 'object_id')},
        ),
    ]
