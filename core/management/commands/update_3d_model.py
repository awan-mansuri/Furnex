from django.core.management.base import BaseCommand
from django.core.files import File
from core.models import Product
import os

class Command(BaseCommand):
    help = 'Update a product with 3D model'

    def add_arguments(self, parser):
        parser.add_argument('product_id', type=int, help='Product ID to update')
        parser.add_argument('model_file', type=str, help='Path to 3D model file (relative to static/models/)')

    def handle(self, *args, **options):
        try:
            product = Product.objects.get(id=options['product_id'])
            model_file_path = f"core/static/models/{options['model_file']}"
            
            if not os.path.exists(model_file_path):
                self.stdout.write(
                    self.style.ERROR(f'Model file not found: {model_file_path}')
                )
                return
            
            with open(model_file_path, 'rb') as f:
                product.model_3d.save(options['model_file'], File(f), save=True)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated product "{product.name}" with 3D model: {options["model_file"]}'
                )
            )
            
        except Product.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Product with ID {options["product_id"]} not found')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating product: {str(e)}')
            )