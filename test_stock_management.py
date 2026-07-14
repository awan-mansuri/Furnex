import os
import sys
import django
from django.conf import settings

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Configure Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'core',
        ],
        SECRET_KEY='test-secret-key',
        USE_TZ=True,
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }],
        MIDDLEWARE=[
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'django.middleware.clickjacking.XFrameOptionsMiddleware',
        ],
    )

django.setup()

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from core.models import Category, Product, VendorPayment, StockManagement
from core.admin import VendorPaymentAdmin

class StockManagementTestCase(TestCase):
    def setUp(self):
        # Create test data
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product',
            category=self.category,
            price=100.00,
            stock=10
        )

    def test_vendor_payment_creates_stock_management(self):
        """Test that saving VendorPayment creates StockManagement entry"""
        # Create VendorPayment
        vendor_payment = VendorPayment.objects.create(
            vendor_name='Test Vendor',
            product_purchased='Test Product',
            quantity_purchased=5,
            purchase_price=80.00,
            total_purchase_amount=400.00,
            payment_made=400.00,
            balance_remaining=0.00
        )

        # Check if StockManagement was created
        stock_entry = StockManagement.objects.filter(product=self.product).first()
        self.assertIsNotNone(stock_entry)
        self.assertEqual(stock_entry.product_quantity, 5)
        self.assertEqual(stock_entry.current_stock, 5)
        self.assertEqual(stock_entry.supplier_name, 'Test Vendor')

    def test_product_save_creates_stock_management(self):
        """Test that saving Product with stock creates StockManagement entry"""
        # Product was already created in setUp with stock=10
        stock_entry = StockManagement.objects.filter(product=self.product).first()
        self.assertIsNotNone(stock_entry)
        self.assertEqual(stock_entry.product_quantity, 10)
        self.assertEqual(stock_entry.current_stock, 10)
        self.assertEqual(stock_entry.supplier_name, 'Initial Stock')

    def test_csv_import_functionality(self):
        """Test CSV import for VendorPayment"""
        # Create test CSV content
        csv_content = """vendor_name,product_purchased,quantity_purchased,purchase_price,total_purchase_amount,payment_made,balance_remaining,notes
Test Vendor,Test Product,3,75.00,225.00,225.00,0.00,Test import
Another Vendor,New Product,2,50.00,100.00,100.00,0.00,Another test"""

        csv_file = SimpleUploadedFile(
            "test_import.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        # Create admin instance
        admin_site = AdminSite()
        vendor_admin = VendorPaymentAdmin(VendorPayment, admin_site)

        # Mock request
        class MockRequest:
            user = User.objects.create_superuser('admin', 'admin@test.com', 'password')

        request = MockRequest()

        # Test import
        try:
            result = vendor_admin.import_csv(request, csv_file)
            # Check if records were created
            vendor_payments = VendorPayment.objects.filter(vendor_name='Test Vendor')
            self.assertTrue(vendor_payments.exists())

            # Check if StockManagement entries were created via signals
            stock_entries = StockManagement.objects.filter(supplier_name='Test Vendor')
            self.assertTrue(stock_entries.exists())

        except Exception as e:
            self.fail(f"CSV import failed: {str(e)}")

if __name__ == '__main__':
    import unittest
    unittest.main()
