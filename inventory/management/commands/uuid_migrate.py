import json
import uuid
from pathlib import Path
from django.core.management.base import BaseCommand
from django.apps import apps
from django.conf import settings


class Command(BaseCommand):
    help = "Migrate all inventory models' primary keys to UUIDs in data dump"

    def get_data_dump(self):
        """Load JSON data from the dump file."""
        path = Path(settings.BASE_DIR) / "mydata.json"
        with open(path, "r") as f:
            return json.load(f)

    def save_data_dump(self, data):
        """Save JSON data back to a new dump file."""
        path = Path(settings.BASE_DIR) / "mydata_updated.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    def get_inventory_models(self):
        """Return a dictionary of all inventory models."""
        return {model._meta.label_lower: model for model in apps.get_app_config("inventory").get_models()}

    def handle(self, *args, **options):
        data = self.get_data_dump()
        id_mapping = {}  # {("app.model", old_id): new_uuid}
        inventory_models = self.get_inventory_models()

        # Step 1: Assign new UUIDs for inventory models only
        for obj in data:
            if obj["model"] in inventory_models:
                new_uuid = str(uuid.uuid4())
                id_mapping[(obj["model"], obj["pk"])] = new_uuid
                obj["pk"] = new_uuid  # Replace primary key with UUID

        # Step 2: Update foreign key references across ALL objects
        for obj in data:
            model_name = obj["model"]
            model = apps.get_model(model_name)  # Get the actual model class

            # Handle normal ForeignKey relations
            for field in model._meta.fields:
                if field.get_internal_type() == "ForeignKey":
                    fk_name = field.name
                    if fk_name in obj["fields"] and obj["fields"][fk_name] is not None:
                        old_fk_id = obj["fields"][fk_name]
                        related_model_label = field.related_model._meta.label_lower
                        if related_model_label not in ('contenttypes.contenttype', 'auth.user'):
                            if (related_model_label, old_fk_id) in id_mapping:
                                obj["fields"][fk_name] = id_mapping[(related_model_label, old_fk_id)]

            # Handle GenericForeignKey (ContentType relations)
            if "content_type" in obj["fields"] and "object_id" in obj["fields"]:
                object_id = obj["fields"]["object_id"]

                if obj["fields"]["content_type"] is not None:
                    related_model_label = ".".join(obj["fields"]["content_type"])
                    if related_model_label and (related_model_label, object_id) in id_mapping:
                        obj["fields"]["object_id"] = id_mapping[(related_model_label, object_id)]

        # Step 3: Save the updated JSON file
        self.save_data_dump(data)
        self.stdout.write(self.style.SUCCESS("Successfully migrated inventory IDs to UUIDs, including ContentType relations. Saved to data_dump_updated.json"))
