#!/usr/bin/env python
"""Check user account and address details"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'furnex.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import UserAddress

print("=" * 60)
print("USER ACCOUNTS CHECK")
print("=" * 60)

users = User.objects.all()
print(f"\nTotal users: {users.count()}\n")

for user in users:
    print(f"Username: {user.username}")
    print(f"Email: {user.email if user.email else '❌ NO EMAIL'}")
    print(f"Is Staff: {user.is_staff}")
    print(f"Is Active: {user.is_active}")
    
    # Check addresses
    addresses = UserAddress.objects.filter(user=user)
    print(f"Addresses: {addresses.count()}")
    
    if addresses.exists():
        for i, addr in enumerate(addresses, 1):
            print(f"  Address {i}:")
            print(f"    - Name: {addr.first_name} {addr.last_name}")
            print(f"    - Phone: {addr.phone if addr.phone else '❌ NO PHONE'}")
            print(f"    - Address: {addr.address}, {addr.city}, {addr.state}")
            print(f"    - Default: {addr.is_default}")
    else:
        print("  ❌ NO ADDRESSES FOUND")
    
    print("-" * 60)

print("\n" + "=" * 60)
print("RECOMMENDATIONS:")
print("=" * 60)

for user in users.filter(is_staff=False):
    issues = []
    
    if not user.email:
        issues.append(f"❌ {user.username}: Add email address")
    
    addresses = UserAddress.objects.filter(user=user)
    if not addresses.exists():
        issues.append(f"❌ {user.username}: Add delivery address")
    else:
        for addr in addresses:
            if not addr.phone:
                issues.append(f"❌ {user.username}: Add phone to address")
    
    if issues:
        for issue in issues:
            print(issue)

print("\n✅ To fix these issues:")
print("1. Login at: http://127.0.0.1:8000/login/")
print("2. Go to Profile: http://127.0.0.1:8000/profile/")
print("3. Click 'Edit Profile' to add email")
print("4. Click 'Add New Address' to add delivery address with phone")
