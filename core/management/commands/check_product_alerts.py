from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from core.models import ProductAlert, Product

class Command(BaseCommand):
    help = 'Check product alerts and send notifications'

    def handle(self, *args, **options):
        """Check all active alerts and send notifications when conditions are met"""
        
        alerts_sent = 0
        
        # 1. Check Back in Stock Alerts
        self.stdout.write(self.style.SUCCESS('Checking back-in-stock alerts...'))
        stock_alerts = ProductAlert.objects.filter(
            alert_type='back_in_stock',
            is_active=True,
            notified=False
        ).select_related('product', 'user')
        
        for alert in stock_alerts:
            if alert.product.stock > 0:
                # Send notification
                try:
                    send_mail(
                        subject=f'🎉 {alert.product.name} is Back in Stock!',
                        message=f'''
Good news! The product you were waiting for is now available.

Product: {alert.product.name}
Price: ₹{alert.product.final_price}
Stock: {alert.product.stock} items available

Don't wait - get yours now!

View Product: {settings.SITE_URL}/product/{alert.product.id}/
                        ''',
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[alert.user.email],
                        fail_silently=False
                    )
                    
                    # Mark as notified
                    alert.notified = True
                    alert.notified_at = timezone.now()
                    alert.is_active = False  # Deactivate after notification
                    alert.save()
                    
                    alerts_sent += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Sent stock alert to {alert.user.email} for {alert.product.name}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Failed to send alert to {alert.user.email}: {str(e)}')
                    )
        
        # 2. Check Price Drop Alerts (compare current price to historical)
        self.stdout.write(self.style.SUCCESS('\nChecking price drop alerts...'))
        # For price drop, you'd need to track historical prices
        # For now, we'll skip this as it requires price history tracking
        
        # 3. Check Target Price Alerts
        self.stdout.write(self.style.SUCCESS('\nChecking target price alerts...'))
        target_alerts = ProductAlert.objects.filter(
            alert_type='price_target',
            is_active=True,
            notified=False
        ).select_related('product', 'user')
        
        for alert in target_alerts:
            if alert.target_price and alert.product.final_price <= alert.target_price:
                # Send notification
                try:
                    send_mail(
                        subject=f'💰 Price Drop Alert: {alert.product.name}',
                        message=f'''
Great news! The product you're watching has reached your target price.

Product: {alert.product.name}
Your Target: ₹{alert.target_price}
Current Price: ₹{alert.product.final_price} ✓

This is your chance to save!

View Product: {settings.SITE_URL}/product/{alert.product.id}/
                        ''',
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[alert.user.email],
                        fail_silently=False
                    )
                    
                    # Mark as notified
                    alert.notified = True
                    alert.notified_at = timezone.now()
                    alert.is_active = False  # Deactivate after notification
                    alert.save()
                    
                    alerts_sent += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Sent price alert to {alert.user.email} for {alert.product.name}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Failed to send alert to {alert.user.email}: {str(e)}')
                    )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Alert check complete. {alerts_sent} notifications sent.')
        )
