#!/usr/bin/env python
"""
Simple email test script for Furnex Django application
Run this to test if your email configuration is working
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'furnex.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email():
    """Test email sending functionality"""
    print("🧪 Testing Email Configuration...")
    print("=" * 50)
    
    # Check current email settings
    print(f"📧 Email Backend: {settings.EMAIL_BACKEND}")
    print(f"🌐 Email Host: {settings.EMAIL_HOST}")
    print(f"🔌 Email Port: {settings.EMAIL_PORT}")
    print(f"🔒 Use TLS: {settings.EMAIL_USE_TLS}")
    print(f"👤 Email User: {settings.EMAIL_HOST_USER}")
    print(f"🔑 Email Password: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 'Not set'}")
    print()
    
    # Test email sending
    try:
        print("📤 Attempting to send test email...")
        
        # Get recipient email from user input
        recipient = input("Enter your email address to receive the test email: ").strip()
        
        if not recipient:
            print("❌ No email address provided. Exiting.")
            return
        
        # Send test email
        send_mail(
            subject='🧪 Test Email from Furnex',
            message=f'''Hello!

This is a test email from your Furnex Django application.

If you received this email, your email configuration is working correctly!

Email settings:
- Backend: {settings.EMAIL_BACKEND}
- Host: {settings.EMAIL_HOST}
- Port: {settings.EMAIL_PORT}
- TLS: {settings.EMAIL_USE_TLS}

Best regards,
Furnex Team''',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[recipient],
            fail_silently=False,
        )
        
        print("✅ Test email sent successfully!")
        print(f"📬 Check your inbox at: {recipient}")
        
    except Exception as e:
        print(f"❌ Failed to send test email: {str(e)}")
        print()
        print("🔧 Troubleshooting tips:")
        print("1. Check your email and password in settings.py")
        print("2. For Gmail, make sure you're using an app password")
        print("3. Check if your firewall/antivirus is blocking SMTP")
        print("4. Verify the SMTP server and port settings")
        print("5. Make sure 2FA is enabled for Gmail accounts")

if __name__ == "__main__":
    test_email() 