import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import Client
from django.contrib import admin


@pytest.mark.django_db
def test_admin_pages_load(client):
    """
    Test if all admin changelist and add pages load successfully.
    """
    # Create a superuser for testing
    User.objects.create_superuser(username="admin", password="password", email="admin@example.com")

    # Log in as the superuser
    client.login(username="admin", password="password")

    # Get all admin URLs (changelist and add pages)
    admin_urls = []
    for model in admin.site._registry.keys():
        app_label = model._meta.app_label
        model_name = model._meta.model_name

        # Changelist page (List view of records)
        changelist_url = reverse(f'admin:{app_label}_{model_name}_changelist')
        admin_urls.append(changelist_url)

        # Add page (Form to add new record)
        add_url = reverse(f'admin:{app_label}_{model_name}_add')
        excluded_urls = [
            '/admin/django_q/success/add/',
            '/admin/django_q/failure/add/',
            '/admin/django_q/ormq/add/',
        ]
        if add_url not in excluded_urls:
            admin_urls.append(add_url)

    # Check if each admin URL loads without errors
    for url in admin_urls:
        response = client.get(url)
        assert response.status_code == 200, f"Admin page {url} failed to load"
