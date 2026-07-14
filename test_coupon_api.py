import os
import django

# Setup Django first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'furnex.settings')
django.setup()

# Now import Django components
from django.test import TestCase, Client
from django.contrib.auth.models import User

from core.models import Coupon, Cart, Product, Category

# Create test client
client = Client()

print("=== Testing Coupon API Endpoints ===")

# Create test user if doesn't exist
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={'email': 'test@example.com', 'password': 'testpass123'}
)
if created:
    user.set_password('testpass123')
    user.save()
    print(f"✓ Created test user: {user.username}")
else:
    print(f"✓ Using existing test user: {user.username}")

# Login user
login_success = client.login(username='testuser', password='testpass123')
print(f"✓ Login {'successful' if login_success else 'failed'}")

if not login_success:
    print("❌ Cannot test coupon endpoints without login")
    exit(1)

# Check if user has coupons
user_coupons = Coupon.objects.filter(user=user, is_active=True)
print(f"✓ User has {user_coupons.count()} active coupons")

if user_coupons.exists():
    test_coupon = user_coupons.first()
    print(f"✓ Testing with coupon: {test_coupon.code}")
    
    # Create test cart item if none exist
    try:
        category = Category.objects.first()
        if not category:
            category = Category.objects.create(name='Test Category', description='Test')
        
        product = Product.objects.first()
        if not product:
            product = Product.objects.create(
                name='Test Product',
                description='Test Product Description',
                price=2000.00,
                category=category,
                stock=10
            )
        
        # Add to cart if not exists
        cart_item, cart_created = Cart.objects.get_or_create(
            user=user,
            product=product,
            defaults={'quantity': 2}
        )
        if cart_created:
            print(f"✓ Added {product.name} to cart")
        else:
            print(f"✓ Cart already has {product.name}")
            
        cart_total = sum(item.total_price for item in Cart.objects.filter(user=user))
        print(f"✓ Cart total: Rs {cart_total}")
        
        # Test apply coupon endpoint
        response = client.post('/apply-coupon/', {'coupon_code': test_coupon.code})
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ Apply coupon endpoint works: {data.get('message')}")
                print(f"  - Discount: Rs {data.get('discount_amount', 0)}")
                print(f"  - New total: Rs {data.get('new_total', 0)}")
            else:
                print(f"❌ Apply coupon failed: {data.get('message')}")
        else:
            print(f"❌ Apply coupon endpoint failed with status {response.status_code}")
        
        # Test remove coupon endpoint
        response = client.post('/remove-coupon/')
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ Remove coupon endpoint works: {data.get('message')}")
                print(f"  - New total: Rs {data.get('new_total', 0)}")
            else:
                print(f"❌ Remove coupon failed: {data.get('message')}")
        else:
            print(f"❌ Remove coupon endpoint failed with status {response.status_code}")
            
        # Test apply-user-coupon endpoint (alias)
        response = client.post('/apply-user-coupon/', {'coupon_code': test_coupon.code})
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ Apply-user-coupon endpoint (alias) works: {data.get('message')}")
            else:
                print(f"❌ Apply-user-coupon failed: {data.get('message')}")
        else:
            print(f"❌ Apply-user-coupon endpoint failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error setting up test data: {e}")

else:
    print("❌ No active coupons found for user. Creating one...")
    from core.views import create_user_coupon
    try:
        coupon = create_user_coupon(
            user=user,
            coupon_type='percentage', 
            amount=10,
            reason='Test Coupon'
        )
        print(f"✓ Created test coupon: {coupon.code}")
        print("Re-run this test to verify the endpoints work with the new coupon.")
    except Exception as e:
        print(f"❌ Failed to create test coupon: {e}")

print("\n=== Test Complete ===")
