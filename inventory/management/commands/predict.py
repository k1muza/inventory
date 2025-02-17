from django.core.management.base import BaseCommand

from inventory.models import Product
from utils.predictor import Predictor

class Command(BaseCommand):
    help = 'Predict sales'

    def handle(self, *args, **options):
        predictor = Predictor()

        for product in Product.objects.filter(predict_demand=True, is_active=True):
            forecasts = predictor.predict_sales(product)
            self.stdout.write(self.style.SUCCESS(f'Product: {product.name}'))
            for forecast in forecasts:
                y = round(forecast['yhat'], 2)
                self.stdout.write(self.style.SUCCESS(f'{forecast["ds"].strftime('%Y-%m-%d')}: {y}'))
