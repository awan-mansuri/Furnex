from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta


# Create your models here.

class UserProfile(models.Model):
    """Extended profile for storing user avatar/profile picture."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

    @property
    def avatar_url(self):
        try:
            return self.avatar.url if self.avatar else None
        except Exception:
            return None

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Categories'

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    # 3D Model field for AR/3D preview
    model_3d = models.FileField(upload_to='models/', blank=True, null=True, help_text='Upload .glb 3D model file for AR/3D preview')
    # Product dimensions
    length = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Length in cm')
    height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Height in cm')
    width = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Width in cm')
    # Add SKU, etc. as needed

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Products'

    @property
    def final_price(self):
        """Return price after subtracting the discount amount (if present)."""
        if self.discount_price:
            return self.price - self.discount_price
        return self.price

    @property
    def average_rating(self):
        data = self.reviews.filter(approved=True).aggregate(avg=Avg('rating'))
        return data['avg'] or 0

class Order(models.Model):
    STATUS_CHOICES = [
        ('placed', 'Order Placed'),
        ('processing', 'Processing'),
        ('dispatched', 'Dispatched'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('returning', 'Returning'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_CHOICES = [
        ('bank_transfer', 'Direct Bank Transfer'),
        ('cheque', 'Cheque Payment'),
        ('paypal', 'PayPal'),
        ('cash_on_delivery', 'Cash on Delivery'),
        ('razorpay', 'Razorpay'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    
    # Billing Information
    first_name = models.CharField(max_length=100, default='')
    last_name = models.CharField(max_length=100, default='')
    company_name = models.CharField(max_length=200, blank=True, default='')
    country = models.CharField(max_length=100, default='')
    address = models.TextField(default='')
    apartment = models.CharField(max_length=200, blank=True, default='')
    state_country = models.CharField(max_length=100, default='')
    postal_zip = models.CharField(max_length=20, default='')
    email = models.EmailField(default='')
    phone = models.CharField(max_length=20, default='')
    
    # Shipping Information (if different)
    ship_to_different = models.BooleanField(default=False)
    ship_first_name = models.CharField(max_length=100, blank=True)
    ship_last_name = models.CharField(max_length=100, blank=True)
    ship_company_name = models.CharField(max_length=200, blank=True)
    ship_country = models.CharField(max_length=100, blank=True)
    ship_address = models.TextField(blank=True)
    ship_apartment = models.CharField(max_length=200, blank=True)
    ship_state_country = models.CharField(max_length=100, blank=True)
    ship_postal_zip = models.CharField(max_length=20, blank=True)
    ship_email = models.EmailField(blank=True)
    ship_phone = models.CharField(max_length=20, blank=True)
    
    # Order Details
    order_notes = models.TextField(blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='bank_transfer')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    # Status timestamps
    placed_at = models.DateTimeField(blank=True, null=True, help_text='When order was placed')
    processing_at = models.DateTimeField(blank=True, null=True, help_text='When order entered processing')
    dispatched_at = models.DateTimeField(blank=True, null=True, help_text='When order was dispatched')
    out_for_delivery_at = models.DateTimeField(blank=True, null=True, help_text='When order went out for delivery')
    delivered_at = models.DateTimeField(blank=True, null=True, help_text='When order was delivered')
    returning_at = models.DateTimeField(blank=True, null=True, help_text='When return was initiated')
    returned_at = models.DateTimeField(blank=True, null=True, help_text='When return was completed')
    cancelled_at = models.DateTimeField(blank=True, null=True, help_text='When order was cancelled')
    
    # Order Tracking
    tracking_id = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text='Unique tracking ID for order')
    
    # Totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Coupon Discount (separate from admin product discounts)
    coupon_code = models.CharField(max_length=50, blank=True, null=True, help_text='Applied coupon code')
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Discount amount from coupon')
    
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Razorpay Integration Fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Operational flags
    stock_deducted = models.BooleanField(default=False, help_text='Has stock been deducted for this order?')
    
    # Return information
    return_reason = models.TextField(blank=True, null=True, help_text='Reason for return if order is being returned')
    return_requested_at = models.DateTimeField(blank=True, null=True, help_text='When return was requested')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f'Order #{self.id} - {self.first_name} {self.last_name}'
    
    @property
    def order_number(self):
        return f'ORD-{self.id:06d}'
    
    def save(self, *args, **kwargs):
        # Preserve previous status to detect transitions precisely
        prev = None
        if self.pk:
            try:
                prev = Order.objects.only('status').get(pk=self.pk)
            except Order.DoesNotExist:
                prev = None

        # Generate tracking ID if not present
        if not self.tracking_id:
            self.tracking_id = self.generate_tracking_id()

        now = timezone.now()
        # Ensure placed_at is set on first save
        if not self.placed_at:
            # If created_at already exists (on update), use it; else use now
            self.placed_at = getattr(self, 'created_at', None) or now

        # If status changed, stamp the appropriate timestamp once
        old_status = prev.status if prev else None
        if self.status and self.status != old_status:
            if self.status == 'processing' and not self.processing_at:
                self.processing_at = now
            elif self.status == 'dispatched' and not self.dispatched_at:
                self.dispatched_at = now
            elif self.status == 'out_for_delivery' and not self.out_for_delivery_at:
                self.out_for_delivery_at = now
            elif self.status == 'delivered' and not self.delivered_at:
                self.delivered_at = now
            elif self.status == 'returning' and not self.returning_at:
                self.returning_at = now
            elif self.status == 'returned' and not self.returned_at:
                self.returned_at = now
            elif self.status == 'cancelled' and not self.cancelled_at:
                self.cancelled_at = now

        # Auto-sync payment_status with final states
        if self.status == 'delivered' and self.payment_status != 'refunded':
            self.payment_status = 'paid'
        elif self.status == 'returned':
            self.payment_status = 'refunded'

        super().save(*args, **kwargs)
    
    def generate_tracking_id(self):
        """Generate a unique tracking ID for the order"""
        import string
        import random
        
        while True:
            # Generate format: FN + 8 random uppercase letters/numbers
            tracking_id = 'FN' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Check if this tracking ID already exists
            if not Order.objects.filter(tracking_id=tracking_id).exists():
                return tracking_id
    
    @property
    def status_display(self):
        """Get the human-readable status"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    
    @property
    def can_return(self):
        """Return True if order is eligible for return (within 10 days of delivery)."""
        if self.status != 'delivered':
            return False
        delivered_on = self.delivered_at or self.updated_at or self.created_at
        return timezone.now() <= (delivered_on + timedelta(days=10))
    
    @property
    def shipping_address(self):
        """Get formatted shipping address"""
        if self.ship_to_different:
            address_parts = [self.ship_address]
            if self.ship_apartment:
                address_parts.append(f"Apt {self.ship_apartment}")
            address_parts.extend([
                self.ship_state_country,
                self.ship_postal_zip,
                self.ship_country
            ])
            return ', '.join(filter(None, address_parts))
        else:
            address_parts = [self.address]
            if self.apartment:
                address_parts.append(f"Apt {self.apartment}")
            address_parts.extend([
                self.state_country,
                self.postal_zip,
                self.country
            ])
            return ', '.join(filter(None, address_parts))
    
    @property
    def shipping_name(self):
        """Get shipping recipient name"""
        if self.ship_to_different:
            return f"{self.ship_first_name} {self.ship_last_name}".strip()
        else:
            return f"{self.first_name} {self.last_name}".strip()

    class Meta:
        verbose_name_plural = 'Orders'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Order item'
        verbose_name_plural = 'Order items'

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['user', 'product'], ['session_key', 'product']]

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    @property
    def total_price(self):
        return self.product.final_price * self.quantity

class Discount(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    USER_TYPES = [
        ('all', 'All Users'),
        ('specific', 'Specific User Only'),
        ('first_order', 'First Order Bonus'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='percentage')
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Enter percentage (e.g., 10 for 10%) or fixed amount')
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='all')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, help_text='Leave blank for all users')
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(default=1, help_text='How many times this coupon can be used')
    used_count = models.PositiveIntegerField(default=0)
    
    # Validity
    valid_from = models.DateTimeField(null=True, blank=True, help_text='Leave blank to start from creation time')
    valid_until = models.DateTimeField(null=True, blank=True, help_text='Leave blank for no expiry')
    
    # Minimum order amount
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Minimum order amount to use this coupon')
    
    active = models.BooleanField(default=True)
    
    # Notification tracking
    user_notified = models.BooleanField(default=False, help_text='Has user been notified about this coupon?')
    awarded_for = models.CharField(max_length=100, blank=True, null=True, help_text='Reason for awarding this coupon (e.g., "First Order", "Loyalty Reward")')
    
    class Meta:
        verbose_name = 'Coupon Code'
        verbose_name_plural = 'Coupon Codes'
        ordering = ['-id']
    
    def __str__(self):
        return f'{self.code} - {self.amount}% off' if self.discount_type == 'percentage' else f'{self.code} - ₹{self.amount} off'
    
    def is_valid(self, user=None, order_amount=0):
        """Check if coupon is valid for use"""
        from django.utils import timezone
        
        # Check if active
        if not self.active:
            return False, 'Coupon is not active'
        
        # Check usage limit
        if self.used_count >= self.usage_limit:
            return False, 'Coupon usage limit exceeded'
        
        # Check validity period
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False, 'Coupon is not yet valid'
        if self.valid_until and now > self.valid_until:
            return False, 'Coupon has expired'
        
        # Check minimum order amount
        if order_amount < self.minimum_order_amount:
            return False, f'Minimum order amount is ₹{self.minimum_order_amount}'
        
        # Check user restrictions
        if self.user_type == 'specific' and self.user != user:
            return False, 'This coupon is not valid for your account'
        
        # Check first order bonus
        if self.user_type == 'first_order' and user:
            from .models import Order
            if Order.objects.filter(user=user, payment_status__in=['paid']).exists():
                return False, 'This coupon is only for first-time customers'
        
        return True, 'Valid coupon'
    
    def get_discount_amount(self, order_total):
        """Calculate discount amount based on type"""
        if self.discount_type == 'percentage':
            return (order_total * self.amount) / 100
        else:
            return min(self.amount, order_total)  # Fixed amount but not more than order total
    
    def use_coupon(self):
        """Increment used count"""
        self.used_count += 1
        self.save()

class EmailQueue(models.Model):
    to = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    html = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    
    def __str__(self):
        return f"EmailQueue to {self.to} ({self.subject})"

class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'

    def __str__(self):
        who = self.user.username if self.user else (self.name or 'Guest')
        return f"{who} on {self.product.name} ({self.rating})"

class UserAddress(models.Model):
    ADDRESS_TYPES = [
        ('billing', 'Billing'),
        ('shipping', 'Shipping'),
        ('both', 'Billing & Shipping'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='both')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company = models.CharField(max_length=200, blank=True, null=True)
    address = models.TextField()
    apartment = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Address'
        verbose_name_plural = 'User Addresses'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.city}, {self.state}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default address per user
        if self.is_default:
            UserAddress.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def full_address(self):
        """Return formatted full address"""
        parts = [self.address]
        if self.apartment:
            parts.append(f"Apt {self.apartment}")
        parts.extend([self.city, f"{self.state} {self.postal_code}", self.country])
        return ", ".join(parts)

class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"

class Coupon(models.Model):
    """User-specific coupon system"""
    DISCOUNT_TYPES = [
        ('flat', 'Flat Discount'),
        ('percent', 'Percentage Discount'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_coupons')
    code = models.CharField(max_length=8, unique=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='flat')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=5000)
    max_uses_per_user = models.PositiveIntegerField(default=2)
    expiry_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Coupon'
        verbose_name_plural = 'User Coupons'
    
    def __str__(self):
        return f"{self.code} - {self.user.username}"
    
    def is_valid(self, user):
        """Check if coupon is valid for the user"""
        from django.utils import timezone
        
        # Check if coupon is active
        if not self.is_active:
            return False, "Coupon is not active"
        
        # Check if coupon belongs to the user
        if self.user != user:
            return False, "This coupon is not valid for your account"
        
        # Check expiry date
        if timezone.now() > self.expiry_date:
            return False, "Coupon has expired"
        
        # Check usage count
        used_count = UserCoupon.objects.filter(user=user, coupon=self).count()
        if used_count >= self.max_uses_per_user:
            return False, f"You have already used this coupon {self.max_uses_per_user} times"
        
        return True, "Valid coupon"
    
    def get_discount_amount(self, order_total):
        """Calculate discount amount based on type"""
        if self.discount_type == 'percent':
            return (order_total * self.discount_value) / 100
        else:  # flat
            return min(self.discount_value, order_total)
    
    def is_expired(self):
        """Check if coupon is expired"""
        from django.utils import timezone
        return timezone.now() > self.expiry_date
    
    def remaining_uses(self, user):
        """Get remaining uses for the user"""
        used_count = UserCoupon.objects.filter(user=user, coupon=self).count()
        return max(0, self.max_uses_per_user - used_count)

class UserCoupon(models.Model):
    """Track coupon usage by users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_usage')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usage_records')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='coupon_used')
    used_at = models.DateTimeField(auto_now_add=True)
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['-used_at']
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
    
    def __str__(self):
        return f"{self.user.username} used {self.coupon.code}"

class Wishlist(models.Model):
    """User wishlist for products"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class Compare(models.Model):
    """Product comparison list for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='compare_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='compared_by')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']
        verbose_name = 'Compare Item'
        verbose_name_plural = 'Compare Items'
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class UserNotification(models.Model):
    """User notifications for coupons and other updates"""
    NOTIFICATION_TYPES = [
        ('coupon_awarded', 'Coupon Awarded'),
        ('coupon_expiring', 'Coupon Expiring'),
        ('order_update', 'Order Update'),
        ('general', 'General Notification'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='general')
    title = models.CharField(max_length=200)
    message = models.TextField()
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Notification'
        verbose_name_plural = 'User Notifications'
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"

# ============================================
# FEATURE 1: Room Design Visualizer
# ============================================

class RoomDesign(models.Model):
    """User's saved room designs"""
    ROOM_TYPES = [
        ('living_room', 'Living Room'),
        ('bedroom', 'Bedroom'),
        ('dining_room', 'Dining Room'),
        ('office', 'Office'),
        ('kitchen', 'Kitchen'),
        ('other', 'Other'),
    ]

# ============================================
# FEATURE 2: Live Chat Support
# ============================================

class ChatConversation(models.Model):
    """Chat conversation between user and support"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_conversations', null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True, help_text='For guest users')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_chats')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    subject = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Chat Conversation'
        verbose_name_plural = 'Chat Conversations'
    
    def __str__(self):
        user_name = self.user.username if self.user else f"Guest {self.session_key[:8]}"
        return f"Chat with {user_name} - {self.status}"

class ChatMessage(models.Model):
    """Individual chat messages"""
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_bot = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    message = models.TextField()
    attachment = models.FileField(upload_to='chat_attachments/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
    
    def __str__(self):
        sender_name = 'Bot' if self.is_bot else (self.sender.username if self.sender else 'Guest')
        return f"{sender_name}: {self.message[:50]}"

class FAQ(models.Model):
    """Simple FAQ entries to power the chatbot without external APIs"""
    question = models.CharField(max_length=255)
    answer = models.TextField()
    tags = models.CharField(max_length=255, blank=True, help_text='Comma-separated keywords')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question[:80]

# ============================================
# FEATURE 3: Smart Size/Dimension Filter
# ============================================

class ProductDimension(models.Model):
    """Product dimensions and specifications"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='dimensions')
    width = models.DecimalField(max_digits=6, decimal_places=2, help_text='Width in inches')
    height = models.DecimalField(max_digits=6, decimal_places=2, help_text='Height in inches')
    depth = models.DecimalField(max_digits=6, decimal_places=2, help_text='Depth in inches')
    weight = models.DecimalField(max_digits=6, decimal_places=2, help_text='Weight in lbs')
    seating_capacity = models.PositiveIntegerField(null=True, blank=True, help_text='For seating furniture')
    material = models.CharField(max_length=200, blank=True)
    assembly_required = models.BooleanField(default=True)
    assembly_time = models.PositiveIntegerField(null=True, blank=True, help_text='Estimated assembly time in minutes')
    
    class Meta:
        verbose_name = 'Product Dimension'
        verbose_name_plural = 'Product Dimensions'
    
    def __str__(self):
        return f"{self.product.name} - {self.width}W x {self.height}H x {self.depth}D"
    
    @property
    def volume(self):
        """Calculate volume in cubic inches"""
        return float(self.width * self.height * self.depth)
    
    @property
    def fits_through_standard_door(self):
        """Check if product fits through standard 36" door"""
        return self.width <= 36 and self.height <= 80

# ============================================
# FEATURE 4: Virtual Showroom Tours
# ============================================

class Showroom(models.Model):
    """Virtual showroom with 360 views"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='showrooms/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Display order')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Showroom'
        verbose_name_plural = 'Showrooms'
    
    def __str__(self):
        return self.name

class ShowroomScene(models.Model):
    """Individual scenes/rooms in a showroom"""
    showroom = models.ForeignKey(Showroom, on_delete=models.CASCADE, related_name='scenes')
    name = models.CharField(max_length=200)
    panorama_image = models.ImageField(upload_to='panoramas/', help_text='360° panoramic image')
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Showroom Scene'
        verbose_name_plural = 'Showroom Scenes'
    
    def __str__(self):
        return f"{self.showroom.name} - {self.name}"

class ShowroomHotspot(models.Model):
    """Product hotspots in panoramic scenes"""
    scene = models.ForeignKey(ShowroomScene, on_delete=models.CASCADE, related_name='hotspots')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    position_x = models.DecimalField(max_digits=5, decimal_places=2, help_text='X position (0-100%)')
    position_y = models.DecimalField(max_digits=5, decimal_places=2, help_text='Y position (0-100%)')
    
    class Meta:
        verbose_name = 'Showroom Hotspot'
        verbose_name_plural = 'Showroom Hotspots'
    
    def __str__(self):
        return f"{self.product.name} in {self.scene.name}"

# ============================================
# FEATURE 6: Group Buying & Gift Registry
# ============================================

class GiftRegistry(models.Model):
    """Gift registry for weddings, housewarmings, etc."""
    REGISTRY_TYPES = [
        ('wedding', 'Wedding'),
        ('housewarming', 'Housewarming'),
        ('birthday', 'Birthday'),
        ('anniversary', 'Anniversary'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gift_registries')
    name = models.CharField(max_length=200, help_text='e.g., "Sarah & John\'s Wedding"')
    registry_type = models.CharField(max_length=20, choices=REGISTRY_TYPES, default='wedding')
    event_date = models.DateField()
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    unique_code = models.CharField(max_length=12, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gift Registry'
        verbose_name_plural = 'Gift Registries'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.unique_code:
            import string
            import random
            self.unique_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        super().save(*args, **kwargs)

class GiftRegistryItem(models.Model):
    """Products in a gift registry"""
    registry = models.ForeignKey(GiftRegistry, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_requested = models.PositiveIntegerField(default=1)
    quantity_purchased = models.PositiveIntegerField(default=0)
    priority = models.CharField(max_length=20, choices=[
        ('high', 'Must Have'),
        ('medium', 'Would Love'),
        ('low', 'Nice to Have'),
    ], default='medium')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Registry Item'
        verbose_name_plural = 'Registry Items'
    
    def __str__(self):
        return f"{self.product.name} for {self.registry.name}"
    
    @property
    def is_fulfilled(self):
        return self.quantity_purchased >= self.quantity_requested

class GroupPurchase(models.Model):
    """Group buying/contribution for expensive items"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_purchases')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deadline = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    unique_code = models.CharField(max_length=12, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Group Purchase'
        verbose_name_plural = 'Group Purchases'
    
    def __str__(self):
        return f"Group Buy: {self.product.name}"
    
    def save(self, *args, **kwargs):
        if not self.unique_code:
            import string
            import random
            self.unique_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        super().save(*args, **kwargs)
    
    @property
    def progress_percentage(self):
        """Calculate funding progress"""
        if self.target_amount > 0:
            return min(100, (float(self.current_amount) / float(self.target_amount)) * 100)
        return 0

class GroupPurchaseContribution(models.Model):
    """Individual contributions to group purchases"""
    group_purchase = models.ForeignKey(GroupPurchase, on_delete=models.CASCADE, related_name='contributions')
    contributor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_contributions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField(blank=True, help_text='Optional message to organizer')
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Group Purchase Contribution'
        verbose_name_plural = 'Group Purchase Contributions'
    
    def __str__(self):
        contributor_name = 'Anonymous' if self.is_anonymous else self.contributor.username
        return f"{contributor_name} - ${self.amount}"

# ============================================
# FEATURE 7: Personalized Recommendations
# ============================================

class UserBrowsingHistory(models.Model):
    """Track user browsing for recommendations"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='browsing_history')
    session_key = models.CharField(max_length=40, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    time_spent = models.PositiveIntegerField(default=0, help_text='Time spent in seconds')
    
    class Meta:
        ordering = ['-viewed_at']
        verbose_name = 'Browsing History'
        verbose_name_plural = 'Browsing History'
    
    def __str__(self):
        user_id = self.user.username if self.user else self.session_key[:8]
        return f"{user_id} viewed {self.product.name}"

class StylePreference(models.Model):
    """User's style preferences from quiz"""
    STYLE_CHOICES = [
        ('modern', 'Modern'),
        ('traditional', 'Traditional'),
        ('minimalist', 'Minimalist'),
        ('rustic', 'Rustic'),
        ('industrial', 'Industrial'),
        ('scandinavian', 'Scandinavian'),
        ('bohemian', 'Bohemian'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='style_preference')
    primary_style = models.CharField(max_length=20, choices=STYLE_CHOICES)
    secondary_style = models.CharField(max_length=20, choices=STYLE_CHOICES, blank=True)
    preferred_colors = models.JSONField(default=list, help_text='List of preferred colors')
    budget_range_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_range_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    room_types = models.JSONField(default=list, help_text='Types of rooms they\'re furnishing')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Style Preference'
        verbose_name_plural = 'Style Preferences'
    
    def __str__(self):
        return f"{self.user.username} - {self.primary_style}"

class ProductRecommendation(models.Model):
    """Store pre-calculated product recommendations"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recommended_with')
    recommended_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recommendations')
    score = models.DecimalField(max_digits=5, decimal_places=2, help_text='Recommendation strength (0-100)')
    reason = models.CharField(max_length=200, blank=True, help_text='Why this is recommended')
    
    class Meta:
        unique_together = ('product', 'recommended_product')
        ordering = ['-score']
        verbose_name = 'Product Recommendation'
        verbose_name_plural = 'Product Recommendations'
    
    def __str__(self):
        return f"{self.product.name} -> {self.recommended_product.name}"

# ============================================
# FEATURE 8: Assembly Service Booking
# ============================================

class AssemblyService(models.Model):
    """Assembly service options"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_item = models.DecimalField(max_digits=10, decimal_places=2, help_text='Additional charge per item')
    estimated_time = models.PositiveIntegerField(help_text='Estimated time in minutes')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Assembly Service'
        verbose_name_plural = 'Assembly Services'
    
    def __str__(self):
        return f"{self.name} - ${self.base_price}"

class ServiceBooking(models.Model):
    """Customer bookings for assembly/installation"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='service_bookings')
    service = models.ForeignKey(AssemblyService, on_delete=models.CASCADE)
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_services')
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    customer_notes = models.TextField(blank=True)
    technician_notes = models.TextField(blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_date', '-scheduled_time']
        verbose_name = 'Service Booking'
        verbose_name_plural = 'Service Bookings'
    
    def __str__(self):
        return f"Service for Order #{self.order.id} on {self.scheduled_date}"

class AssemblyVideo(models.Model):
    """Assembly tutorial videos for products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='assembly_videos')
    title = models.CharField(max_length=200)
    video_url = models.URLField(help_text='YouTube or video URL')
    thumbnail = models.ImageField(upload_to='assembly_thumbnails/', blank=True, null=True)
    duration = models.PositiveIntegerField(help_text='Duration in seconds')
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Assembly Video'
        verbose_name_plural = 'Assembly Videos'

    def __str__(self):
        return f"{self.product.name} - {self.title}"

# ============================================
# USER ACTIVITY LOGGING
# ============================================

class UserActivity(models.Model):
    """Log user activities for admin monitoring"""
    ACTION_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('register', 'User Registration'),
        ('view_product', 'View Product'),
        ('add_to_cart', 'Add to Cart'),
        ('remove_from_cart', 'Remove from Cart'),
        ('place_order', 'Place Order'),
        ('cancel_order', 'Cancel Order'),
        ('return_order', 'Return Order'),
        ('add_to_wishlist', 'Add to Wishlist'),
        ('remove_from_wishlist', 'Remove from Wishlist'),
        ('add_to_compare', 'Add to Compare'),
        ('remove_from_compare', 'Remove from Compare'),
        ('search', 'Search'),
        ('contact_form', 'Contact Form Submission'),
        ('review_product', 'Review Product'),
        ('update_profile', 'Update Profile'),
        ('change_password', 'Change Password'),
        ('page_view', 'Page View'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    session_key = models.CharField(max_length=40, null=True, blank=True, help_text='For guest users')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, help_text='Additional details about the activity')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, help_text='Browser user agent')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        user_name = self.user.username if self.user else f"Guest ({self.session_key[:8]}...)" if self.session_key else "Anonymous"
        return f"{user_name} - {self.get_action_display()} at {self.timestamp}"

class BackInStockAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='back_in_stock_alerts')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='back_in_stock_alerts')
    is_active = models.BooleanField(default=True)
    notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.product.name} back in stock alert"

# ============================================
# PRODUCT PURCHASE AND VENDOR PAYMENT MODELS
# ============================================

class StockManagement(models.Model):
    """Model to manage stock details for products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_batches', null=True, blank=True, help_text='Associated product (set when deployed)')
    product_category = models.ForeignKey(Category, on_delete=models.CASCADE, help_text='Category of the product')
    product_name = models.CharField(max_length=200, help_text='Name of the product')
    product_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price per unit of the product')
    product_quantity = models.PositiveIntegerField(help_text='Quantity purchased/added to stock')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Total price (price * quantity)')
    current_stock = models.PositiveIntegerField(default=0, help_text='Current available stock')
    supplier_name = models.CharField(max_length=200, blank=True, help_text='Supplier or vendor name')
    purchase_date = models.DateTimeField(auto_now_add=True, help_text='Date and time of purchase/stock addition')
    # Product dimensions
    length = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Length in cm')
    height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Height in cm')
    width = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Width in cm')

    class Meta:
        verbose_name = 'Stock Management'
        verbose_name_plural = 'Stock Management'
        ordering = ['-purchase_date']

    def __str__(self):
        return f"{self.product_name} - Stock: {self.current_stock} units"

    def save(self, *args, **kwargs):
        # Auto-calculate total_price if not provided
        if not self.total_price:
            self.total_price = self.product_price * self.product_quantity
        # Update current_stock if not set
        if self.current_stock == 0:
            self.current_stock = self.product_quantity
        super().save(*args, **kwargs)

class VendorPayment(models.Model):
    """Model to track payments made to vendors for product purchases"""
    vendor_name = models.CharField(max_length=200, help_text='Name of the vendor')
    product_purchased = models.CharField(max_length=200, help_text='Name of the product purchased from vendor')
    quantity_purchased = models.PositiveIntegerField(help_text='Quantity purchased from this vendor')
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price per unit paid to vendor')
    total_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Total amount for this purchase (price * quantity)')
    payment_made = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Amount already paid to vendor')
    balance_remaining = models.DecimalField(max_digits=10, decimal_places=2, help_text='Remaining balance to be paid')
    payment_date = models.DateTimeField(auto_now_add=True, help_text='Date when payment record was created')
    notes = models.TextField(blank=True, help_text='Additional notes about the payment')
    # Product dimensions
    length = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Length in cm')
    height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Height in cm')
    width = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Width in cm')

    # ✅ Allow NULL values to avoid IntegrityError
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Category of the product purchased'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Linked product if applicable'
    )

    class Meta:
        verbose_name = 'Product Purchase'
        verbose_name_plural = 'Product Purchases'
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.vendor_name} - {self.product_purchased} - Balance: ₹{self.balance_remaining}"

    def save(self, *args, **kwargs):
        # Auto-calculate total_purchase_amount and balance_remaining
        if not self.total_purchase_amount:
            self.total_purchase_amount = self.purchase_price * self.quantity_purchased
        self.balance_remaining = self.total_purchase_amount - self.payment_made
        super().save(*args, **kwargs)


class Vendor(models.Model):
    """Aggregated vendor summary of purchases and payments."""
    name = models.CharField(max_length=200, unique=True)
    total_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_left = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'
        ordering = ['name']

    def __str__(self):
        return self.name