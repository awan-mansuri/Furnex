from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Order


class Command(BaseCommand):
    help = 'Update orders from returning to returned status after 2 days'

    def handle(self, *args, **options):
        # Calculate the date 2 days ago
        two_days_ago = timezone.now() - timedelta(days=2)
        
        # Find orders that are in 'returning' status and were requested more than 2 days ago
        orders_to_update = Order.objects.filter(
            status='returning',
            return_requested_at__lte=two_days_ago
        )
        
        count = orders_to_update.count()
        
        if count > 0:
            # Update the orders to 'returned' status
            orders_to_update.update(status='returned')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {count} order(s) from "returning" to "returned" status.'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('No orders found to update.')
            )
