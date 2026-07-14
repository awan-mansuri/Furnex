import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'furnex.settings')
django.setup()

from core.models import Coupon, User, Cart

print("=== All Coupons ===")
coupons = Coupon.objects.all()
for c in coupons:
    print(f"{c.code} - User: {c.user.username} - Type: {c.discount_type} - Value: {c.discount_value} - Active: {c.is_active}")
    print(f"  Min Order: {c.min_order_value} - Expires: {c.expiry_date}")

if coupons.exists():
    print("\n=== Testing First Coupon ===")
    c = coupons.first()
    print(f"Testing coupon: {c.code}")
    
    # Test validity
    is_valid, msg = c.is_valid(c.user)
    print(f"Valid for owner: {is_valid} - {msg}")
    
    # Test discount calculation
    test_amount = 10000
    discount = c.get_discount_amount(test_amount)
    print(f"Discount for Rs {test_amount}: Rs {discount}")
    
    # Check if user has cart items
    cart_items = Cart.objects.filter(user=c.user)
    print(f"User {c.user.username} cart items: {cart_items.count()}")
    
    if cart_items.exists():
        subtotal = sum(item.total_price for item in cart_items)
        print(f"Cart subtotal: Rs {subtotal}")
        
        # Test min order validation
        if subtotal >= c.min_order_value:
            print("✓ Cart meets minimum order value")
        else:
            print(f"✗ Cart below minimum order value (need Rs {c.min_order_value})")