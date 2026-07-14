import random
import string
from datetime import timedelta
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Order, Coupon, UserNotification, Cart, Wishlist, Compare, Review, Contact, UserActivity, Product, BackInStockAlert
from django.urls import reverse


# ============================================
# USER ACTIVITY LOGGING SIGNALS
# ============================================

def create_notification_from_activity(activity):
    """Create user notification based on activity type"""
    if not activity.user:
        return

    notification_data = {
        'user': activity.user,
        'notification_type': 'general',
        'title': '',
        'message': ''
    }

    if activity.action == 'register':
        notification_data.update({
            'notification_type': 'general',
            'title': 'Welcome to Furnex!',
            'message': 'Welcome to Furnex Furniture Store! Start exploring our amazing collection of furniture.'
        })
    elif activity.action == 'place_order':
        notification_data.update({
            'notification_type': 'order_update',
            'title': f'Order #{activity.details.get("order_id")} Placed Successfully!',
            'message': f'Your order #{activity.details.get("order_id")} has been placed successfully. Total: ₹{activity.details.get("total")}. We will notify you when it ships.'
        })
    elif activity.action == 'cancel_order':
        notification_data.update({
            'notification_type': 'order_update',
            'title': f'Order #{activity.details.get("order_id")} Cancelled',
            'message': f'Your order #{activity.details.get("order_id")} has been cancelled. If you have any questions, please contact our support team.'
        })
    elif activity.action == 'return_order':
        notification_data.update({
            'notification_type': 'order_update',
            'title': f'Order #{activity.details.get("order_id")} Return Initiated',
            'message': f'Your return request for order #{activity.details.get("order_id")} has been initiated. We will process it within 2-3 business days.'
        })
    elif activity.action == 'add_to_cart':
        notification_data.update({
            'notification_type': 'general',
            'title': f'Added to Cart: {activity.details.get("product_name")}',
            'message': f'{activity.details.get("product_name")} has been added to your cart.'
        })
    elif activity.action == 'remove_from_cart':
        notification_data.update({
            'notification_type': 'general',
            'title': f'Removed from Cart: {activity.details.get("product_name")}',
            'message': f'{activity.details.get("product_name")} has been removed from your cart.'
        })
    elif activity.action == 'add_to_wishlist':
        notification_data.update({
            'notification_type': 'general',
            'title': f'Added to Wishlist: {activity.details.get("product_name")}',
            'message': f'{activity.details.get("product_name")} has been added to your wishlist.'
        })
    elif activity.action == 'remove_from_wishlist':
        notification_data.update({
            'notification_type': 'general',
            'title': f'Removed from Wishlist: {activity.details.get("product_name")}',
            'message': f'{activity.details.get("product_name")} has been removed from your wishlist.'
        })
    elif activity.action == 'add_to_compare':
        notification_data.update({
            'notification_type': 'general',
            'title': f'Added to Compare: {activity.details.get("product_name")}',
            'message': f'{activity.details.get("product_name")} has been added to your compare list.'
        })
    elif activity.action == 'remove_from_compare':
        notification_data.update({
            'notification_type': 'general',
            'title': f'Removed from Compare: {activity.details.get("product_name")}',
            'message': f'{activity.details.get("product_name")} has been removed from your compare list.'
        })
    elif activity.action == 'review_product':
        notification_data.update({
            'notification_type': 'general',
            'title': f'Review Submitted for {activity.details.get("product_name")}',
            'message': f'Thank you for reviewing {activity.details.get("product_name")}! Your feedback helps other customers.'
        })
    elif activity.action == 'update_profile':
        notification_data.update({
            'notification_type': 'general',
            'title': 'Profile Updated',
            'message': 'Your profile information has been successfully updated.'
        })
    elif activity.action == 'change_password':
        notification_data.update({
            'notification_type': 'general',
            'title': 'Password Changed',
            'message': 'Your password has been successfully changed. Please use your new password for future logins.'
        })
    elif activity.action == 'login':
        notification_data.update({
            'notification_type': 'general',
            'title': 'Welcome Back!',
            'message': f'Welcome back, {activity.user.username}! You have successfully logged in.'
        })
    elif activity.action == 'logout':
        notification_data.update({
            'notification_type': 'general',
            'title': 'Logged Out',
            'message': 'You have been successfully logged out. Thank you for visiting Furnex!'
        })
    elif activity.action == 'search':
        notification_data.update({
            'notification_type': 'general',
            'title': 'Search Performed',
            'message': f'You searched for: {activity.details.get("query", "N/A")}'
        })
    elif activity.action == 'page_view':
        notification_data.update({
            'notification_type': 'general',
            'title': 'Page Viewed',
            'message': f'You viewed: {activity.details.get("page", "N/A")}'
        })
    elif activity.action == 'deliver_order':
        notification_data.update({
            'notification_type': 'order_update',
            'title': f'Order #{activity.details.get("order_id")} Delivered!',
            'message': f'Great news! Your order #{activity.details.get("order_id")} has been delivered successfully. Enjoy your new furniture!'
        })
    elif activity.action == 'ship_order':
        notification_data.update({
            'notification_type': 'order_update',
            'title': f'Order #{activity.details.get("order_id")} Shipped!',
            'message': f'Your order #{activity.details.get("order_id")} has been shipped and is on its way. Track your order for updates.'
        })
    elif activity.action == 'coupon_awarded':
        notification_data.update({
            'notification_type': 'coupon_awarded',
            'title': f'New Coupon Awarded: {activity.details.get("coupon_code")}',
            'message': f'Congratulations! You have been awarded a coupon: {activity.details.get("coupon_code")}. {activity.details.get("discount_text")} on orders above ₹{activity.details.get("min_order_value")}. Valid until {activity.details.get("expiry_date")}.'
        })

    # Create notification if we have valid data
    if notification_data['title'] and notification_data['message']:
        UserNotification.objects.create(**notification_data)


# ============================================
# USER ACTIVITY LOGGING SIGNALS
# ============================================

def log_user_activity(user, session_key, action, details=None, request=None):
    """Helper function to log user activities"""
    if not details:
        details = {}

    ip_address = None
    user_agent = ''

    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

    # Create UserActivity log
    activity = UserActivity.objects.create(
        user=user,
        session_key=session_key,
        action=action,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Create corresponding UserNotification if user exists
    if user:
        create_notification_from_activity(activity)


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@receiver(post_save, sender=User)
def log_user_registration(sender, instance, created, **kwargs):
    """Log user registration"""
    if created:
        log_user_activity(
            instance,
            None,
            'register',
            {'email': instance.email, 'username': instance.username}
        )


@receiver(post_save, sender=Order)
def log_order_activities(sender, instance, created, **kwargs):
    """Log order-related activities"""
    if created:
        log_user_activity(
            instance.user,
            instance.session_key,
            'place_order',
            {
                'order_id': instance.id,
                'total': str(instance.total),
                'payment_method': instance.payment_method
            }
        )
    else:
        # Check for status changes
        if hasattr(instance, '_original_status'):
            if instance._original_status != instance.status:
                if instance.status == 'cancelled':
                    log_user_activity(
                        instance.user,
                        instance.session_key,
                        'cancel_order',
                        {'order_id': instance.id, 'reason': getattr(instance, 'cancel_reason', '')}
                    )
                elif instance.status == 'returning':
                    log_user_activity(
                        instance.user,
                        instance.session_key,
                        'return_order',
                        {'order_id': instance.id, 'reason': instance.return_reason}
                    )
                elif instance.status == 'delivered':
                    log_user_activity(
                        instance.user,
                        instance.session_key,
                        'deliver_order',
                        {'order_id': instance.id}
                    )
                elif instance.status == 'shipped':
                    log_user_activity(
                        instance.user,
                        instance.session_key,
                        'ship_order',
                        {'order_id': instance.id}
                    )


@receiver(post_save, sender=Cart)
def log_cart_activities(sender, instance, created, **kwargs):
    """Log cart add/remove activities"""
    if created:
        log_user_activity(
            instance.user,
            instance.session_key,
            'add_to_cart',
            {
                'product_id': instance.product.id,
                'product_name': instance.product.name,
                'quantity': instance.quantity
            }
        )


@receiver(post_delete, sender=Cart)
def log_cart_removal(sender, instance, **kwargs):
    """Log cart item removal"""
    log_user_activity(
        instance.user,
        instance.session_key,
        'remove_from_cart',
        {
            'product_id': instance.product.id,
            'product_name': instance.product.name
        }
    )


@receiver(post_save, sender=Wishlist)
def log_wishlist_activities(sender, instance, created, **kwargs):
    """Log wishlist add activities"""
    if created:
        log_user_activity(
            instance.user,
            None,
            'add_to_wishlist',
            {
                'product_id': instance.product.id,
                'product_name': instance.product.name
            }
        )


@receiver(post_delete, sender=Wishlist)
def log_wishlist_removal(sender, instance, **kwargs):
    """Log wishlist item removal"""
    log_user_activity(
        instance.user,
        None,
        'remove_from_wishlist',
        {
            'product_id': instance.product.id,
            'product_name': instance.product.name
        }
    )


@receiver(post_save, sender=Compare)
def log_compare_activities(sender, instance, created, **kwargs):
    """Log compare add activities"""
    if created:
        log_user_activity(
            instance.user,
            None,
            'add_to_compare',
            {
                'product_id': instance.product.id,
                'product_name': instance.product.name
            }
        )


@receiver(post_delete, sender=Compare)
def log_compare_removal(sender, instance, **kwargs):
    """Log compare item removal"""
    log_user_activity(
        instance.user,
        None,
        'remove_from_compare',
        {
            'product_id': instance.product.id,
            'product_name': instance.product.name
        }
    )


@receiver(post_save, sender=Review)
def log_review_activity(sender, instance, created, **kwargs):
    """Log product review submission"""
    if created:
        log_user_activity(
            instance.user,
            None,
            'review_product',
            {
                'product_id': instance.product.id,
                'product_name': instance.product.name,
                'rating': instance.rating
            }
        )


@receiver(post_save, sender=Contact)
def log_contact_form(sender, instance, created, **kwargs):
    """Log contact form submission"""
    if created:
        log_user_activity(
            None,
            None,
            'contact_form',
            {
                'email': instance.email,
                'subject': instance.message[:50] + '...' if len(instance.message) > 50 else instance.message
            }
        )


@receiver(post_save, sender=Coupon)
def log_coupon_activities(sender, instance, created, **kwargs):
    """Log coupon-related activities"""
    if created:
        # Log coupon awarded activity
        if instance.user:
            discount_text = f'{instance.discount_value}% off' if instance.discount_type == 'percent' else f'₹{instance.discount_value} off'
            log_user_activity(
                instance.user,
                None,
                'coupon_awarded',
                {
                    'coupon_code': instance.code,
                    'discount_text': discount_text,
                    'min_order_value': instance.min_order_value,
                    'expiry_date': str(instance.expiry_date.date())
                }
            )

# ============================================
# BACK IN STOCK NOTIFICATIONS
# ============================================
from django.db.models.signals import pre_save

@receiver(pre_save, sender=Product)
def capture_old_stock(sender, instance, **kwargs):
    """Store previous stock on the instance before save so post_save can compare."""
    if instance.pk:
        try:
            old = Product.objects.only('stock').get(pk=instance.pk)
            instance._old_stock = old.stock
        except Product.DoesNotExist:
            instance._old_stock = None
    else:
        instance._old_stock = None

@receiver(post_save, sender=Product)
def notify_back_in_stock(sender, instance, created, **kwargs):
    """When stock transitions from 0 to >0, notify users with active alerts."""
    try:
        old_stock = getattr(instance, '_old_stock', None)
        if old_stock == 0 and instance.stock > 0:
            alerts = BackInStockAlert.objects.filter(product=instance, is_active=True, notified=False).select_related('user')
            if not alerts.exists():
                return
            # Create notifications for all alerting users
            to_create = []
            for alert in alerts:
                to_create.append(UserNotification(
                    user=alert.user,
                    notification_type='general',
                    title='Back in Stock',
                    message=f'{instance.name} is back in stock. Hurry before it sells out again!'
                ))
            UserNotification.objects.bulk_create(to_create)
            # Mark alerts as notified and inactive
            alerts.update(notified=True, is_active=False)
    except Exception:
        # Do not raise; keep save flow robust
        pass
