import random
import string
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Coupon, UserNotification


class Command(BaseCommand):
    help = 'Generate coupon for a specific user'
    
    def add_arguments(self, parser):
        parser.add_argument('--user_id', type=int, required=True, help='User ID for whom to generate coupon')
        parser.add_argument('--discount_type', type=str, required=True, choices=['flat', 'percent'], help='Discount type: flat or percent')
        parser.add_argument('--discount_value', type=float, required=True, help='Discount value (amount for flat, percentage for percent)')
        parser.add_argument('--min_order_value', type=float, default=5000, help='Minimum order value (default: 5000)')
        parser.add_argument('--max_uses', type=int, default=2, help='Maximum uses per user (default: 2)')
        parser.add_argument('--valid_days', type=int, default=30, help='Valid for how many days (default: 30)')
    
    def handle(self, *args, **options):
        try:
            # Get user
            user = User.objects.get(id=options['user_id'])
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with ID {options["user_id"]} does not exist'))
            return
        
        # Generate unique 8-character code
        code = self.generate_unique_code()
        
        # Calculate expiry date
        expiry_date = timezone.now() + timedelta(days=options['valid_days'])
        
        # Create coupon
        coupon = Coupon.objects.create(
            user=user,
            code=code,
            discount_type=options['discount_type'],
            discount_value=options['discount_value'],
            min_order_value=options['min_order_value'],
            max_uses_per_user=options['max_uses'],
            expiry_date=expiry_date
        )
        
        # Create notification for user
        if options['discount_type'] == 'flat':
            notification_message = f"Congratulations! You've received a ₹{options['discount_value']} discount coupon. Use code '{code}' at checkout."
            display_value = f"₹{options['discount_value']} off"
        else:
            notification_message = f"Congratulations! You've received a {options['discount_value']}% discount coupon. Use code '{code}' at checkout."
            display_value = f"{options['discount_value']}% off"
        
        UserNotification.objects.create(
            user=user,
            notification_type='coupon_awarded',
            title=f"New Coupon: {code}",
            message=notification_message,
            coupon=coupon
        )
        
        # Output success message in the exact format requested
        self.stdout.write(
            self.style.SUCCESS(
                f'Coupon generated for {user.username}: {code} | {options["discount_type"]} {options["discount_value"]} | expires {expiry_date.strftime("%Y-%m-%d")}'
            )
        )
    
    def generate_unique_code(self):
        """Generate unique 8-character alphanumeric code"""
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(characters, k=8))
            if not Coupon.objects.filter(code=code).exists():
                return code