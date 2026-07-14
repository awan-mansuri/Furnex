from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
import razorpay
from django.conf import settings
from .models import (Product, Category, Order, OrderItem, Cart, Review, Discount, Contact, UserAddress, 
                     UserNotification, Coupon, UserCoupon, Wishlist, Compare, UserProfile,
                     GiftRegistry, GiftRegistryItem, GroupPurchase,
                     GroupPurchaseContribution, AssemblyService, ServiceBooking, UserBrowsingHistory,
                     StylePreference, ProductRecommendation, ChatConversation, ChatMessage, BackInStockAlert)
from django.contrib.auth.models import User, Group
from django.db.models.functions import TruncMonth, Coalesce
from django.db.models import DecimalField
from django.db import models as dj_models
from django.utils import timezone
from datetime import timedelta
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.db.models import Sum, Count
from .forms import UserRegisterForm, UserProfileForm, UserAddressForm
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .utils_email import send_smart_email, retry_email_queue
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
try:
    import razorpay  # type: ignore
except Exception:
    razorpay = None
from django.views.decorators.csrf import csrf_exempt
import logging
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction
from django.contrib.admin.views.decorators import staff_member_required
from .utils_sms import send_sms
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.http import HttpResponse
from django.urls import reverse

def mask_email(email):
    """Helper function to mask email addresses for security"""
    if not email or len(email) <= 6:
        return email
    return email[:3] + '*' * (len(email) - 6) + email[-3:]

def set_session_cookie(*args, **kwargs):
    """Deprecated: Cookie management handled by PathBasedSessionMiddleware."""
    return None

def home(request):
    products = Product.objects.all().order_by('-id')  # Show latest products first
    categories = Category.objects.all()
    latest_products = Product.objects.order_by('-id')[:3]  # Use id for latest products
    
    # Check for COD success message from session
    cod_success_message = request.session.pop('cod_success_message', None)
    if cod_success_message:
        messages.success(request, cod_success_message)
    
    return render(request, 'index.html', {
        'products': products,
        'categories': categories,
        'latest_products': latest_products,
    })

def about(request):
    return render(request, 'about.html')

def shop(request):
    category_id = request.GET.get('category')
    q = request.GET.get('q','').strip()
    price_min = request.GET.get('min')
    price_max = request.GET.get('max')
    categories = Category.objects.all()
    
    # Use discounted effective price for filtering and order by latest first
    products = Product.objects.all().annotate(
        effective_price=F('price') - Coalesce(F('discount_price'), 0, output_field=DecimalField(max_digits=10, decimal_places=2))
    ).order_by('-id')  # Show latest products first
    if category_id:
        products = products.filter(category_id=category_id)
    if q:
        products = products.filter(name__icontains=q)
    if price_min:
        try:
            products = products.filter(effective_price__gte=float(price_min))
        except Exception:
            pass
    if price_max:
        try:
            products = products.filter(effective_price__lte=float(price_max))
        except Exception:
            pass
    return render(request, 'shop.html', {
        'products': products,
        'categories': categories,
        'selected_category': category_id,
        'q': q,
        'price_min': price_min,
        'price_max': price_max
    })

def product_detail(request, product_id: int):
    product = Product.objects.get(id=product_id)
    reviews = product.reviews.filter(approved=True)
    
    # Check if product is in user's wishlist
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()
    
    return render(request, 'product_detail.html', {
        'product': product,
        'reviews': reviews,
        'avg_rating': product.average_rating,
        'review_count': reviews.count(),
        'in_wishlist': in_wishlist,
    })

@require_POST
def review_submit(request, product_id: int):
    product = Product.objects.get(id=product_id)
    rating = int(request.POST.get('rating', 0))
    comment = request.POST.get('comment', '')
    name = request.POST.get('name', '')
    if rating >= 1 and rating <= 5:
        Review.objects.create(
            product=product,
            user=request.user if request.user.is_authenticated else None,
            name=name,
            rating=rating,
            comment=comment,
            approved=True
        )
        messages.success(request, 'Thank you for your review!')
    else:
        messages.error(request, 'Please select a rating between 1 and 5.')
    return redirect('product_detail', product_id=product.id)

def services(request):
    return render(request, 'services.html')

def contact(request):
    if request.method == 'POST':
        first_name = request.POST.get('fname', '').strip()
        last_name = request.POST.get('lname', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()
        
        if not all([first_name, last_name, email, message]):
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                # Save contact message to database
                contact = Contact.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    message=message
                )
                
                # Send email notification to admin
                try:
                    admin_email = getattr(settings, 'ADMIN_EMAIL', settings.EMAIL_HOST_USER)
                    subject = f"New Contact Message from {first_name} {last_name}"
                    html_message = f"""
                    <h3>New Contact Message</h3>
                    <p><strong>Name:</strong> {first_name} {last_name}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Message:</strong></p>
                    <p>{message}</p>
                    <p><strong>Date:</strong> {timezone.now().strftime('%Y-%m-%d %H:%M')}</p>
                    """
                    plain_message = f"Name: {first_name} {last_name}\nEmail: {email}\nMessage: {message}\nDate: {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                    
                    send_smart_email(
                        subject=subject,
                        body=plain_message,
                        to=admin_email,
                        html=html_message
                    )
                except Exception as e:
                    logging.warning(f"Contact email notification failed: {e}")
                
                messages.success(request, 'Thank you for your message! We will get back to you soon.')
                return redirect('contact')
                
            except Exception as e:
                messages.error(request, 'There was an error sending your message. Please try again.')
    
    return render(request, 'contact.html')

def blog(request):
    return render(request, 'blog.html')

def cart(request):
    # Show friendly alert and redirect to login for unauthenticated users
    if not request.user.is_authenticated:
        messages.warning(request, 'Please login first to use the cart.')
        login_url = f"{reverse('login')}?next={request.path}"
        return redirect(login_url)

    cart_items = Cart.objects.filter(user=request.user)
    total_price = sum(item.total_price for item in cart_items)
    
    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
    })

@login_required
def checkout_view(request):
    # Only for authenticated users
    cart_items = Cart.objects.filter(user=request.user)
    user_addresses = UserAddress.objects.filter(user=request.user)
    
    # Check if cart is empty
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty. Please add some items before checkout.')
        return redirect('cart')
    
    # Calculate totals
    subtotal = sum(item.total_price for item in cart_items)
    
    # Check for applied coupon (user-specific Coupon or global Discount)
    coupon_discount = Decimal('0')
    applied_coupon = None  # Can be Coupon or Discount instance
    coupon_type = request.session.get('applied_coupon_type', 'user')
    
    if coupon_type == 'discount' and request.session.get('applied_discount_id'):
        try:
            disc = Discount.objects.get(id=request.session.get('applied_discount_id'))
            is_valid, _ = disc.is_valid(request.user, order_amount=subtotal)
            if is_valid:
                applied_coupon = disc
                coupon_discount = Decimal(str(request.session.get('coupon_discount_amount', 0)))
            else:
                for key in ['applied_discount_id', 'applied_coupon_type', 'coupon_discount_amount']:
                    if key in request.session:
                        del request.session[key]
        except Discount.DoesNotExist:
            for key in ['applied_discount_id', 'applied_coupon_type', 'coupon_discount_amount']:
                if key in request.session:
                    del request.session[key]
    else:
        coupon_id = request.session.get('applied_coupon_id')
        if coupon_id:
            try:
                coup = Coupon.objects.get(id=coupon_id)
                is_valid, _ = coup.is_valid(request.user)
                if is_valid and subtotal >= coup.min_order_value:
                    applied_coupon = coup
                    coupon_discount = Decimal(str(request.session.get('coupon_discount_amount', 0)))
                else:
                    for key in ['applied_coupon_id', 'coupon_discount_amount', 'applied_coupon_type']:
                        if key in request.session:
                            del request.session[key]
            except Coupon.DoesNotExist:
                for key in ['applied_coupon_id', 'coupon_discount_amount', 'applied_coupon_type']:
                    if key in request.session:
                        del request.session[key]
    
    total = subtotal - coupon_discount  # Apply coupon discount
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'applied_coupon': applied_coupon,
        'coupon_discount': coupon_discount,
        'total': total,
        'user_addresses': user_addresses,
        'is_guest': not request.user.is_authenticated,
    }
    
    return render(request, 'checkout.html', context)

def thankyou_view(request):
    order = None
    order_id = request.session.get('order_id')
    
    if order_id:
        try:
            order = Order.objects.get(id=order_id)
            # Clear the order_id from session after displaying
            del request.session['order_id']
        except Order.DoesNotExist:
            pass
    
    return render(request, 'thankyou.html', {'order': order})

def merge_session_cart_to_user(request, user):
    """Merge guest (session) cart items into the user's cart after login without touching stock.
    This preserves quantities already reserved by previous add_to_cart calls.
    """
    try:
        session_key = request.session.session_key
        if not session_key:
            return
        guest_items = Cart.objects.filter(session_key=session_key)
        if not guest_items.exists():
            return
        for gi in guest_items:
            user_item, created = Cart.objects.get_or_create(
                user=user,
                product=gi.product,
                defaults={'quantity': gi.quantity}
            )
            if not created:
                # Just add quantities together; stock was already deducted during adds
                user_item.quantity = user_item.quantity + gi.quantity
                user_item.save(update_fields=['quantity'])
            gi.delete()
    except Exception:
        # Best-effort merge; do not block login on errors
        pass


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Merge any guest cart into the logged-in user's cart
            merge_session_cart_to_user(request, user)

            # Admin redirection BEFORE any messages/notifications
            next_url = request.GET.get('next')
            if user.is_staff or (next_url and '/admin' in next_url):
                # Clear any pending messages so none appear in admin
                try:
                    storage = messages.get_messages(request)
                    for _ in storage:
                        pass
                    storage.used = True
                except Exception:
                    pass
                # Prefer explicit admin redirect
                return redirect(next_url if (next_url and '/admin' in next_url) else '/admin/')

            # Site flow (non-admin)
            try:
                UserNotification.objects.create(
                    user=user,
                    notification_type='general',
                    title='Welcome Back!',
                    message=f'Welcome back, {user.username}! You have successfully logged in.'
                )
            except Exception:
                pass
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')

            # Professional HTML Email
            subject = "Welcome to Furnex - Your Account Has Been Created!"
            html_message = render_to_string('registration_email.html', {
                'username': username,
                'site_name': 'Furnex Furniture Store',
            })
            plain_message = f"Hi {username},\n\nThanks for signing up on our Furniture Store website! We're excited to have you with us.\n\nBest regards,\nThe Furnex Team"
            from_email = settings.EMAIL_HOST_USER
            recipient_list = [email]

            try:
                send_smart_email(
                    subject=subject,
                    body=plain_message,
                    to=recipient_list[0],
                    html=html_message
                )
            except Exception as e:
                logging.warning("Registration email enqueue/send failed: %s", e)

            # Auto-login the user after successful registration
            try:
                raw_password = form.cleaned_data.get('password1') or form.cleaned_data.get('password')
                user_auth = authenticate(request, username=username, password=raw_password) if raw_password else None
                if user_auth is None:
                    # Fallback: directly login with default backend if authenticate not possible
                    login(request, user)
                else:
                    login(request, user_auth)
                # Merge any guest cart items
                try:
                    merge_session_cart_to_user(request, user)
                except Exception:
                    pass
                # Create a friendly notification (best-effort)
                try:
                    UserNotification.objects.create(
                        user=user,
                        notification_type='general',
                        title='Welcome!',
                        message=f'Welcome, {username}! Your account has been created.'
                    )
                except Exception:
                    pass
            except Exception:
                pass

            messages.success(request, f'Welcome {username}! You are now logged in.')
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = UserRegisterForm()
    return render(request, 'register.html', {'form': form})

def admin_login_view(request):
    """Custom admin login view that uses separate session cookies"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            
            # Redirect to admin; cookies handled by middleware
            return redirect('/admin/')
        else:
            messages.error(request, 'Invalid admin credentials.')
    return render(request, 'admin/login.html')

def logout_view(request):
    if request.user.is_authenticated:
        try:
            UserNotification.objects.create(
                user=request.user,
                notification_type='general',
                title='Logged Out',
                message='You have been successfully logged out. Thank you for visiting Furnex!'
            )
        except Exception:
            pass
    logout(request)
    return redirect('home')



def password_reset_view(request):
    """Custom password reset view"""
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            associated_users = User.objects.filter(email=email)
            if associated_users.exists():
                for user in associated_users:
                    subject = "Password Reset Request - Furnex"
                    c = {
                        "email": user.email,
                        'domain': request.META['HTTP_HOST'],
                        'site_name': 'Furnex',
                        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                        "user": user,
                        'token': default_token_generator.make_token(user),
                        'protocol': 'https' if request.is_secure() else 'http',
                    }
                    email_html = render_to_string('password_reset_email.html', c)
                    email_text = render_to_string('password_reset_email.txt', c)
                    try:
                        from django.core.mail import EmailMultiAlternatives
                        msg = EmailMultiAlternatives(subject, email_text, 'noreply@furnex.com', [user.email])
                        msg.attach_alternative(email_html, "text/html")
                        msg.send()
                        # Store email in session for masking
                        request.session['reset_email'] = user.email
                        messages.success(request, 'Password reset email has been sent to your email address.')
                        return redirect('password_reset_done')
                    except Exception as e:
                        messages.error(request, 'Failed to send password reset email. Please try again.')
            else:
                # Don't reveal if email exists or not for security
                # Store the requested email in session for masking
                request.session['reset_email'] = email
                messages.success(request, 'Password reset email has been sent to your email address.')
                return redirect('password_reset_done')
    else:
        form = PasswordResetForm()
    
    return render(request, 'password_reset.html', {'form': form})

def password_reset_done_view(request):
    """Password reset done view"""
    # Get the email from session or request
    email = request.session.get('reset_email', '')
    masked_email = mask_email(email) if email else 'your email address'
    
    return render(request, 'password_reset_done.html', {'masked_email': masked_email})

def password_reset_confirm_view(request, uidb64, token):
    """Password reset confirm view"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Your password has been set successfully. You can now log in.')
                return redirect('password_reset_complete')
        else:
            form = SetPasswordForm(user)
        return render(request, 'password_reset_confirm.html', {'form': form})
    else:
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('password_reset')

def password_reset_complete_view(request):
    """Password reset complete view"""
    # Get the email from session for masking
    email = request.session.get('reset_email', '')
    masked_email = mask_email(email) if email else 'your account'
    
    # Clear the session data
    if 'reset_email' in request.session:
        del request.session['reset_email']
    
    return render(request, 'password_reset_complete.html', {'masked_email': masked_email})

# Cart Management Functions
def add_to_cart(request):
    """Add a product to the cart (atomic to handle rapid taps/concurrent requests)."""
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        try:
            quantity = int(request.POST.get('quantity', 1))
        except Exception:
            quantity = 1
        if quantity < 1:
            quantity = 1
        
        try:
            with transaction.atomic():
                # Lock product row to avoid stock race conditions
                product = Product.objects.select_for_update().get(id=product_id)
                
                # Check stock availability for this increment
                if quantity > product.stock:
                    return JsonResponse({'success': False, 'message': 'Not enough stock available.'})
                
                # Add to cart for authenticated users or guest session
                if request.user.is_authenticated:
                    cart_item, created = Cart.objects.get_or_create(
                        user=request.user,
                        product=product,
                        defaults={'quantity': 0}
                    )
                else:
                    if not request.session.session_key:
                        request.session.create()
                    session_key = request.session.session_key
                    cart_item, created = Cart.objects.get_or_create(
                        session_key=session_key,
                        product=product,
                        defaults={'quantity': 0}
                    )
                
                # Increment quantity safely (we already checked stock for this add)
                cart_item.quantity = cart_item.quantity + quantity
                cart_item.save(update_fields=['quantity'])
                
                # Decrease product stock immediately after adding to cart
                product.stock -= quantity
                product.save(update_fields=['stock'])
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Product not found.'})
        except Exception:
            return JsonResponse({'success': False, 'message': 'Could not add to cart. Please try again.'})
        
        messages.success(request, f'{product.name} added to cart!')
        return JsonResponse({
            'success': True,
            'message': f'{product.name} added to cart!',
            'cart_count': get_cart_count(request),
            'product_id': product.id,
            'updated_stock': product.stock
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

def buy_now(request, product_id: int):
    """Buy the selected product only. Clears existing cart items (restoring stock) before adding this item, then redirects to checkout."""
    if request.method != 'POST':
        return redirect('shop')

    # Require auth for checkout flow
    if not request.user.is_authenticated:
        login_url = f"{reverse('login')}?next={reverse('checkout')}"
        return redirect(login_url)

    # Fetch product
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        messages.error(request, 'Product not found.')
        return redirect('shop')
    if product.stock <= 0:
        messages.error(request, 'This product is out of stock.')
        return redirect('shop')

    # Desired quantity from client
    try:
        desired_qty = int(request.POST.get('quantity', 1))
    except Exception:
        desired_qty = 1
    if desired_qty < 1:
        desired_qty = 1
    if desired_qty > product.stock:
        desired_qty = product.stock

    # Clear existing cart items and restore stock so Buy Now is isolated
    try:
        with transaction.atomic():
            user_cart_items = Cart.objects.filter(user=request.user)
            for item in user_cart_items:
                # restore stock for each removed item
                item.product.stock += item.quantity
                item.product.save(update_fields=['stock'])
            user_cart_items.delete()
    except Exception:
        # Do not block Buy Now on cleanup issues
        pass

    # Add only the Buy Now product to cart
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': desired_qty}
    )
    if not created:
        cart_item.quantity = desired_qty
        cart_item.save(update_fields=['quantity'])

    # Decrease product stock immediately after adding to cart
    product.stock -= desired_qty
    product.save(update_fields=['stock'])

    return redirect('checkout')

def update_cart(request):
    """Update cart item quantity"""
    if request.method == 'POST':
        cart_item_id = request.POST.get('cart_item_id')
        quantity = int(request.POST.get('quantity', 1))
        
        try:
            if request.user.is_authenticated:
                cart_item = Cart.objects.get(id=cart_item_id, user=request.user)
            else:
                cart_item = Cart.objects.get(id=cart_item_id, session_key=request.session.session_key)
            
            if quantity <= 0:
                # Restore stock when item is removed
                cart_item.product.stock += cart_item.quantity
                cart_item.product.save(update_fields=['stock'])
                cart_item.delete()
                messages.success(request, 'Item removed from cart.')
            elif quantity > cart_item.product.stock + cart_item.quantity:
                messages.error(request, 'Not enough stock available.')
            else:
                # Adjust stock for quantity change
                delta = quantity - cart_item.quantity
                cart_item.product.stock -= delta
                cart_item.product.save(update_fields=['stock'])
                cart_item.quantity = quantity
                cart_item.save()
                messages.success(request, 'Cart updated successfully.')
            
            return JsonResponse({
                'success': True,
                'cart_count': get_cart_count(request),
                'updated_stock': cart_item.product.stock if quantity > 0 else None
            })
            
        except Cart.DoesNotExist:
            messages.error(request, 'Cart item not found.')
            return JsonResponse({'success': False, 'message': 'Cart item not found.'})
    
    return redirect('cart')

def remove_from_cart(request, cart_item_id):
    """Remove an item from the cart"""
    try:
        if request.user.is_authenticated:
            cart_item = Cart.objects.get(id=cart_item_id, user=request.user)
        else:
            cart_item = Cart.objects.get(id=cart_item_id, session_key=request.session.session_key)
        
        product_name = cart_item.product.name
        # Restore stock when item is removed
        cart_item.product.stock += cart_item.quantity
        cart_item.product.save(update_fields=['stock'])
        cart_item.delete()
        messages.success(request, f'{product_name} removed from cart.')
        
    except Cart.DoesNotExist:
        messages.error(request, 'Cart item not found.')
    
    return redirect('cart')

def get_cart_count(request):
    """Get the total number of items in cart for user or guest session"""
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).aggregate(total=Sum('quantity'))['total'] or 0
    # Guest session
    session_key = request.session.session_key
    if not session_key:
        return 0
    return Cart.objects.filter(session_key=session_key).aggregate(total=Sum('quantity'))['total'] or 0

@require_http_methods(["POST"])
def apply_coupon(request):
    """Apply coupon code and calculate discount - Using new Coupon model"""
    coupon_code = request.POST.get('coupon_code', '').strip().upper()
    
    if not coupon_code:
        return JsonResponse({'success': False, 'message': 'Please enter a coupon code.'})
    
    # Get cart total for authenticated users
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user)
    else:
        return JsonResponse({'success': False, 'message': 'Please login to apply coupons.'})
    
    if not cart_items.exists():
        return JsonResponse({'success': False, 'message': 'Your cart is empty.'})
    
    subtotal = sum(item.total_price for item in cart_items)
    
    try:
        # Find coupon using new Coupon model
        coupon = Coupon.objects.get(code=coupon_code)
        
        # Validate coupon
        is_valid, error_message = coupon.is_valid(request.user)
        
        if not is_valid:
            return JsonResponse({'success': False, 'message': error_message})
        
        # Check minimum order value
        if subtotal < coupon.min_order_value:
            return JsonResponse({
                'success': False, 
                'message': f'Minimum order value is ₹{coupon.min_order_value}. Current cart value: ₹{subtotal}'
            })
        
        # Calculate discount
        discount_amount = coupon.get_discount_amount(subtotal)
        new_total = subtotal - discount_amount
        
        # Store in session using consistent variable names
        request.session['applied_coupon_id'] = coupon.id
        request.session['coupon_discount_amount'] = float(discount_amount)
        
        return JsonResponse({
            'success': True,
            'message': f'Coupon applied successfully! You saved ₹{discount_amount:.2f}',
            'discount_amount': float(discount_amount),
            'new_total': float(new_total),
            'coupon_code': coupon_code
        })
        
    except Coupon.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid coupon code.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Error applying coupon. Please try again.'})

@require_http_methods(["POST"])
def remove_coupon(request):
    """Remove applied coupon - Using consistent session variables"""
    # Clear coupon from session using consistent variable names
    if 'applied_coupon_id' in request.session:
        del request.session['applied_coupon_id']
    if 'coupon_discount_amount' in request.session:
        del request.session['coupon_discount_amount']
    
    # Calculate new total
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user)
        subtotal = sum(item.total_price for item in cart_items)
    else:
        subtotal = 0
    
    return JsonResponse({
        'success': True,
        'message': 'Coupon removed successfully.',
        'new_total': float(subtotal)
    })

@login_required
def process_order(request):
    """Process order from checkout form (COD or other offline-friendly methods).
    Deduct stock immediately for COD orders.
    """
    # Only for authenticated users
    
    if request.method == 'POST':
        # Debug: Print POST data
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"=== PROCESS ORDER CALLED ===")
        logger.error(f"User: {request.user.username}")
        logger.error(f"User email: {request.user.email}")
        logger.error(f"Payment method: {request.POST.get('payment_method')}")
        logger.error(f"Address ID: {request.POST.get('selected_address_id')}")
        # Get cart items for authenticated user
        cart_items = Cart.objects.filter(user=request.user)
        
        # Check if cart is empty
        if not cart_items.exists():
            messages.error(request, 'Your cart is empty. Please add some items before checkout.')
            return redirect('cart')
        
        # Handle address for authenticated users
        selected_address_id = request.POST.get('selected_address_id')
        
        if not selected_address_id:
            messages.error(request, 'Please select a delivery address.')
            return redirect('checkout')
            
        try:
            selected_address = UserAddress.objects.get(id=selected_address_id, user=request.user)
            first_name = selected_address.first_name
            last_name = selected_address.last_name
            email = request.user.email  # Use user's email
            phone = selected_address.phone or ''
            address = selected_address.address
            city = selected_address.city
            state = selected_address.state
            postal_code = selected_address.postal_code
            country = selected_address.country
            company = selected_address.company or ''
            apartment = selected_address.apartment or ''
            order_notes = request.POST.get('c_order_notes', '')
        except UserAddress.DoesNotExist:
            messages.error(request, 'Selected address not found.')
            return redirect('checkout')
        
        # Validate required fields
        if not first_name or not last_name:
            messages.error(request, 'Please provide first name and last name in your address.')
            return redirect('checkout')
        
        if not email:
            messages.error(request, 'Please add an email address to your account. Go to Profile → Edit Profile.')
            return redirect('checkout')
        
        if not phone:
            messages.error(request, 'Please provide a phone number in your address.')
            return redirect('checkout')
        
        if not all([address, state, postal_code, country]):
            messages.error(request, 'Please ensure your address has all required fields (address, state, postal code, country).')
            return redirect('checkout')
        
        try:
            # Calculate totals
            subtotal = sum(item.total_price for item in cart_items)
            
            # Handle coupon discount (supports user Coupon or global Discount)
            applied_coupon = None  # Coupon or Discount instance for display
            coupon_discount = Decimal('0')
            coupon_type = request.session.get('applied_coupon_type', 'user')
            
            if coupon_type == 'discount' and request.session.get('applied_discount_id'):
                try:
                    disc = Discount.objects.get(id=request.session.get('applied_discount_id'))
                    is_valid, _ = disc.is_valid(request.user, order_amount=subtotal)
                    if is_valid:
                        applied_coupon = disc
                        coupon_discount = Decimal(str(request.session.get('coupon_discount_amount', 0)))
                    else:
                        for key in ['applied_discount_id', 'applied_coupon_type', 'coupon_discount_amount']:
                            if key in request.session:
                                del request.session[key]
                        coupon_discount = Decimal('0')
                        applied_coupon = None
                except Discount.DoesNotExist:
                    for key in ['applied_discount_id', 'applied_coupon_type', 'coupon_discount_amount']:
                        if key in request.session:
                            del request.session[key]
                    coupon_discount = Decimal('0')
                    applied_coupon = None
            else:
                coupon_id = request.session.get('applied_coupon_id')
                if coupon_id:
                    try:
                        coupon = Coupon.objects.get(id=coupon_id)
                        is_valid, _ = coupon.is_valid(request.user)
                        
                        if is_valid and subtotal >= coupon.min_order_value:
                            applied_coupon = coupon
                            coupon_discount = Decimal(str(request.session.get('coupon_discount_amount', 0)))
                        else:
                            # Coupon no longer valid, clear from session
                            for key in ['applied_coupon_id', 'coupon_discount_amount', 'applied_coupon_type']:
                                if key in request.session:
                                    del request.session[key]
                            coupon_discount = Decimal('0')
                            applied_coupon = None
                    except Coupon.DoesNotExist:
                        # Coupon deleted, clear from session
                        for key in ['applied_coupon_id', 'coupon_discount_amount', 'applied_coupon_type']:
                            if key in request.session:
                                del request.session[key]
                        coupon_discount = Decimal('0')
                        applied_coupon = None
            
            cod_selected = request.POST.get('payment_method') in ['cod', 'cash_on_delivery']
            cod_fee = Decimal(str(settings.COD_EXTRA_FEE)) if cod_selected else Decimal('0')
            
            # Apply discounts: subtotal - coupon_discount + cod_fee
            total = subtotal - coupon_discount + cod_fee
            
            # Create order
            order = Order.objects.create(
                user=request.user,
                first_name=first_name,
                last_name=last_name,
                company_name=company,
                email=email,
                phone=phone,
                address=address,
                apartment=apartment,
                state_country=state,
                postal_zip=postal_code,
                country=country,
                order_notes=order_notes,
                subtotal=subtotal,
                coupon_code=applied_coupon.code if applied_coupon else None,
                coupon_discount=coupon_discount,
                total=total,
                status='pending',
                payment_method=('cash_on_delivery' if request.POST.get('payment_method') in ['cod','cash_on_delivery'] else request.POST.get('payment_method','razorpay'))
            )
            
            # Create order items
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.final_price
                )
            
            # Deduct stock immediately for COD to reserve inventory
            
            
            # Track coupon usage only for user-specific Coupon
            if coupon_type == 'user' and isinstance(applied_coupon, Coupon) and coupon_discount > 0:
                UserCoupon.objects.create(
                    user=request.user,
                    coupon=applied_coupon,
                    order=order,
                    discount_applied=coupon_discount
                )
            
            # Send order confirmation email
            try:
                eta_date = (timezone.now() + timedelta(days=getattr(settings, 'ORDER_DELIVERY_DAYS', 5))).date()
                html_message = render_to_string('registration_email_order.html', {
                    'order': order,
                    'eta_date': eta_date,
                    'site_url': request.build_absolute_uri('/')[:-1],
                    'cod_fee': settings.COD_EXTRA_FEE if cod_selected else 0,
                })
                send_smart_email(
                    subject=f'Order Confirmation #{order.id} – Furnex',
                    body=f'Thank you for your order #{order.id}.',
                    to=order.email,
                    html=html_message
                )
                # SMS notify
                if phone:
                    eta_str = eta_date.strftime('%Y-%m-%d')
                    send_sms(phone, f'Furnex: Order #{order.id} confirmed. ETA {eta_str}. Total Rs. {int(total)}.')
            except Exception as e:
                logging.warning(f"Email send failed for order {order.id}: {e}")

            # Clear the cart
            cart_items.delete()
            
            # Clear coupon session data
            for key in ['applied_coupon_id', 'applied_discount_id', 'applied_coupon_type', 'coupon_discount_amount']:
                if key in request.session:
                    del request.session[key]
            
            # Store order ID in session for thank you page
            request.session['order_id'] = order.id
            
            # Check if this is user's first order and award coupon
            is_first_order = not Order.objects.filter(
                user=request.user,
                created_at__lt=order.created_at
            ).exists()
            
            if is_first_order:
                try:
                    # Award 10% discount coupon for next order
                    create_user_coupon(
                        user=request.user,
                        coupon_type='percentage',
                        amount=10,
                        reason='First Order Bonus'
                    )
                except Exception as e:
                    logging.warning(f"Failed to create first order coupon for user {request.user.id}: {e}")
            
            if cod_selected:
                order.payment_status = 'pending'
                order.status = 'processing'
                order.save()
                # Store COD success message in session instead of messages framework
                success_msg = f'Your order #{order.id} has been placed with Cash on Delivery! 🎉'
                if is_first_order:
                    success_msg += ' You\'ve also received a 10% discount coupon for your next order!'
                request.session['cod_success_message'] = success_msg
            else:
                success_msg = f'Your order #{order.id} has been placed successfully!'
                if is_first_order:
                    success_msg += ' You\'ve also received a 10% discount coupon for your next order!'
                messages.success(request, success_msg)
            return redirect('thankyou')
            
        except Exception as e:
            messages.error(request, 'There was an error processing your order. Please try again.')
            return redirect('checkout')
    
    # If not POST, redirect to checkout
    return redirect('checkout')

# =============================================================================
# RAZORPAY PAYMENT INTEGRATION
# =============================================================================

# Initialize Razorpay client (optional)
razorpay_client = None
try:
    if razorpay and getattr(settings, 'RAZORPAY_KEY_ID', None) and getattr(settings, 'RAZORPAY_KEY_SECRET', None):
        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception:
    razorpay_client = None

def create_razorpay_order(request):
    """Create Razorpay order and return order details"""
    # Require login for payment
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login to proceed with payment.'})
    
    if request.method == 'POST':
        # Block online payment when offline mode is enabled
        if getattr(settings, 'OFFLINE_MODE', False):
            return JsonResponse({'success': False, 'message': 'Online payment is unavailable in offline mode. Please choose Cash on Delivery.'})
        if not razorpay_client:
            return JsonResponse({'success': False, 'message': 'Online payment is not configured. Please choose Cash on Delivery.'})
        # Get cart items for authenticated user
        cart_items = Cart.objects.filter(user=request.user)
        
        # Check if cart is empty
        if not cart_items.exists():
            return JsonResponse({'success': False, 'message': 'Your cart is empty.'})
        
        # Extract address from selected_address_id
        selected_address_id = request.POST.get('selected_address_id')
        if not selected_address_id:
            return JsonResponse({'success': False, 'message': 'Please select a delivery address.'})
        try:
            selected_address = UserAddress.objects.get(id=selected_address_id, user=request.user)
            first_name = selected_address.first_name
            last_name = selected_address.last_name
            email = request.user.email
            phone = selected_address.phone or ''
            address = selected_address.address
            state = selected_address.state
            postal_code = selected_address.postal_code
            country = selected_address.country
            order_notes = request.POST.get('c_order_notes', '')
        except UserAddress.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Selected address not found.'})

        # Validate required fields
        if not all([first_name, last_name, email, phone, address, state, postal_code, country]):
            return JsonResponse({'success': False, 'message': 'Please fill in all required fields.'})
        
        try:
            # Calculate totals
            subtotal = sum(item.total_price for item in cart_items)
            total = subtotal
            
            # Create Django order first
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                session_key=request.session.session_key if not request.user.is_authenticated else None,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                address=address,
                state_country=state,
                postal_zip=postal_code,
                country=country,
                order_notes=order_notes,
                payment_method='razorpay',
                subtotal=subtotal,
                total=total,
                status='pending',
                payment_status='pending'
            )
            
            # Create order items
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.final_price
                )
            
            # Create Razorpay order
            razorpay_order_data = {
                'amount': int(total * 100),  # Amount in paisa (multiply by 100)
                'currency': 'INR',
                'receipt': f'order_{order.id}',
                'notes': {
                    'order_id': str(order.id),
                    'customer_name': f'{first_name} {last_name}',
                    'customer_email': email
                }
            }
            
            razorpay_order = razorpay_client.order.create(data=razorpay_order_data)
            
            # Save Razorpay order ID to Django order
            order.razorpay_order_id = razorpay_order['id']
            order.save()
            
            # Store order ID in session for later use
            request.session['pending_order_id'] = order.id
            
            return JsonResponse({
                'success': True,
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount': razorpay_order['amount'],
                'currency': razorpay_order['currency'],
                'name': 'Furnex',
                'description': f'Order #{order.id}',
                'order_id': order.id,
                'customer': {
                    'name': f'{first_name} {last_name}',
                    'email': email,
                    'contact': phone
                }
            })
            
        except Exception as e:
            logging.error(f'Error creating Razorpay order: {str(e)}')
            return JsonResponse({'success': False, 'message': 'Failed to create payment order. Please try again.'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@csrf_exempt
@require_POST
def razorpay_payment_success(request):
    """Handle successful Razorpay payment"""
    # Require login for payment success
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login to proceed with payment.'})
    
    try:
        if getattr(settings, 'OFFLINE_MODE', False) or not razorpay_client:
            return JsonResponse({'success': False, 'message': 'Online payment is not available.'})
        # Get payment details from request
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_signature = request.POST.get('razorpay_signature')
        
        # Verify payment signature
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        # Verify the payment signature
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Find the order
        try:
            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Order not found.'})
        
        # Update order with payment details
        order.razorpay_payment_id = razorpay_payment_id
        order.razorpay_signature = razorpay_signature
        order.payment_status = 'paid'
        order.status = 'processing'
        order.save()
        
        # Deduct stock on successful online payment (if not already deducted)
        
        
        # Send order confirmation email with tracking ID
        try:
            eta_date = (timezone.now() + timedelta(days=getattr(settings, 'ORDER_DELIVERY_DAYS', 5))).date()
            html_message = render_to_string('registration_email_order.html', {
                'order': order,
                'eta_date': eta_date,
                'site_url': request.build_absolute_uri('/')[:-1],
                'cod_fee': 0,
            })
            send_smart_email(
                subject=f'Order Confirmation #{order.id} – Furnex',
                body=f'Thank you for your order #{order.id}.',
                to=order.email,
                html=html_message
            )
        except Exception as e:
            logging.warning(f"Email send failed for order {order.id}: {e}")
        
        # Clear the cart
        Cart.objects.filter(user=request.user).delete()
        
        # Store order ID for thank you page
        request.session['order_id'] = order.id
        
        # Clear pending order ID
        if 'pending_order_id' in request.session:
            del request.session['pending_order_id']
        
        return JsonResponse({
            'success': True,
            'message': 'Payment successful!',
            'redirect_url': '/thankyou/'
        })
        
    except Exception as e:
        # Includes signature verification failure or other errors
        logging.error(f'Razorpay processing failed: {str(e)}')
        return JsonResponse({'success': False, 'message': 'Payment verification failed.'})
    

@csrf_exempt
def razorpay_payment_failure(request):
    """Handle failed Razorpay payment"""
    try:
        # Get the pending order ID from session
        order_id = request.session.get('pending_order_id')
        
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.payment_status = 'failed'
                order.status = 'cancelled'
                order.save()
                
                # Clear pending order ID
                del request.session['pending_order_id']
                
            except Order.DoesNotExist:
                pass
        
        return JsonResponse({
            'success': False,
            'message': 'Payment failed. Please try again.',
            'redirect_url': '/checkout/'
        })
        
    except Exception as e:
        logging.error(f'Error processing payment failure: {str(e)}')
        return JsonResponse({'success': False, 'message': 'Error processing payment failure.'})

def payment_success_view(request):
    """Display payment success page"""
    order = None
    order_id = request.session.get('order_id')
    
    if order_id:
        try:
            order = Order.objects.get(id=order_id, payment_status='paid')
        except Order.DoesNotExist:
            pass
    
    return render(request, 'payment_success.html', {'order': order})

def payment_failure_view(request):
    """Display payment failure page"""
    return render(request, 'payment_failure.html')


@staff_member_required
def admin_model_counts(request):
    # Consider paid/prepaid and COD orders that are in progress or completed
    paid_orders = Order.objects.filter(
        dj_models.Q(payment_status='paid') |
        dj_models.Q(payment_method='cash_on_delivery', status__in=['processing', 'shipped', 'delivered'])
    )
    total_revenue = paid_orders.aggregate(total=Sum('total'))['total'] or 0
    return JsonResponse({
        'core': {
            'Categories': Category.objects.count(),
            'Products': Product.objects.count(),
            'Orders': Order.objects.count(),
            'OrderItems': OrderItem.objects.count(),
            'Discounts': Discount.objects.count(),
            'Revenue': float(total_revenue),
        },
        'auth': {
            'Users': User.objects.filter(is_staff=False).count(),
            'Groups': Group.objects.count(),
        }
    })

@staff_member_required
def admin_invoice_view(request, order_id: int):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found')
        return redirect('admin:index')
    return render(request, 'invoice_admin.html', { 'order': order })

def invoice_view(request, order_id: int):
    try:
        if request.user.is_authenticated and request.user.is_staff:
            order = Order.objects.get(id=order_id)
        elif request.user.is_authenticated:
            order = Order.objects.get(id=order_id, user=request.user)
        else:
            # Allow anonymous users who placed order via guest checkout using session key
            order = Order.objects.get(id=order_id, session_key=request.session.session_key)
    except Order.DoesNotExist:
        messages.error(request, 'Invoice not available')
        return redirect('home')
    return render(request, 'invoice.html', { 'order': order, 'COD_FEE': getattr(settings, 'COD_EXTRA_FEE', 0) })

def invoice_pdf(request, order_id: int):
    # Simple PDF invoice using ReportLab
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return HttpResponse('Order not found', status=404)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="invoice_{order_id}.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 50
    p.setFont("Helvetica-Bold", 16)
    p.drawString(40, y, "Furnex Invoice")
    y -= 30
    p.setFont("Helvetica", 11)
    p.drawString(40, y, f"Invoice #: {order.id}")
    y -= 20
    # Tracking ID
    if order.tracking_id:
        p.drawString(40, y, f"Tracking ID: {order.tracking_id}")
        y -= 20
    p.drawString(40, y, f"Date: {order.created_at.strftime('%Y-%m-%d')}")
    y -= 30
    p.drawString(40, y, f"Bill To: {order.first_name} {order.last_name}")
    y -= 20
    p.drawString(40, y, f"Address: {order.address}, {order.state_country} {order.postal_zip}, {order.country}")
    y -= 30
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "Items")
    y -= 20
    p.setFont("Helvetica", 11)
    for item in order.items.all():
        line_price = int(item.price)
        total_line_price = int(item.price * item.quantity)
        product_name = item.product.name
        
        # Show discount info if applicable
        if item.product.discount_price:
            original_price = int(item.product.price)
            discount_amount = int(item.product.discount_price)
            product_name += f" (Was Rs. {original_price}, -{discount_amount} off)"
        
        p.drawString(40, y, f"{product_name} x{item.quantity}")
        p.drawRightString(width-40, y, f"Rs. {line_price} each")
        y -= 18
        if y < 80:
            p.showPage(); y = height - 50
        
        # Show line total
        p.drawString(60, y, f"Line total:")
        p.drawRightString(width-40, y, f"Rs. {total_line_price}")
        y -= 18
        if y < 80:
            p.showPage(); y = height - 50
    y -= 10
    p.line(40, y, width-40, y)
    y -= 20
    p.drawString(40, y, "Subtotal")
    p.drawRightString(width-40, y, f"Rs. {int(order.subtotal)}")
    y -= 18
    if order.payment_method == 'cash_on_delivery':
        p.drawString(40, y, "Cash on Delivery Fee")
        p.drawRightString(width-40, y, f"Rs. {getattr(settings, 'COD_EXTRA_FEE', 0)}")
        y -= 18
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "Total")
    p.drawRightString(width-40, y, f"Rs. {int(order.total)}")
    p.showPage()
    p.save()
    return response


@staff_member_required
def admin_dashboard(request):
    # Redirect staff to Django admin which uses our overridden template
    return redirect('/admin/')


@staff_member_required
def admin_dashboard_data(request):
    """Return JSON data for admin dashboard charts (sales, profit, product sales)."""
    # Determine last 6 months
    now = timezone.now()
    months = []
    for i in range(5, -1, -1):
        dt = (now - timedelta(days=30 * i)).replace(day=1)
        months.append(dt)

    # Paid/qualifying orders
    qualifying_orders = Order.objects.filter(
        dj_models.Q(payment_status='paid') |
        dj_models.Q(payment_method='cash_on_delivery', status__in=['processing', 'shipped', 'delivered'])
    )

    # Sales by month using Order.total to incorporate discounts and fees
    sales_by_month_qs = (
        qualifying_orders
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total_amount=Sum('total'))
    )
    sales_map = {row['month'].date(): float(row['total_amount'] or 0) for row in sales_by_month_qs}

    # Build ordered label/data arrays
    sales_labels = []
    sales_data = []
    profit_data = []
    for dt in months:
        key = dt.date()
        label = dt.strftime('%b %Y')
        amt = round(sales_map.get(key, 0), 2)
        # Simple profit estimate as 22% margin in absence of COGS data
        profit = round(amt * 0.22, 2)
        sales_labels.append(label)
        sales_data.append(amt)
        profit_data.append(profit)

    # Top product sales (quantity) across qualifying orders (last 6 months)
    start_dt = months[0]
    top_products_qs = (
        OrderItem.objects
        .filter(order__in=qualifying_orders, order__created_at__gte=start_dt)
        .values('product__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:8]
    )
    product_sales_labels = [row['product__name'] for row in top_products_qs]
    product_sales_data = [int(row['total_qty'] or 0) for row in top_products_qs]
    
    # Order Status Distribution
    from django.contrib.auth.models import User
    order_status_qs = (
        Order.objects
        .values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )
    order_status_labels = []
    order_status_data = []
    for row in order_status_qs:
        status = row['status']
        count = row['count']
        # Capitalize status names for display
        status_display = status.replace('_', ' ').title()
        order_status_labels.append(status_display)
        order_status_data.append(count)
    
    # User Registration Trend (last 6 months)
    user_registration_labels = []
    user_registration_data = []
    for dt in months:
        key = dt.date()
        label = dt.strftime('%b %Y')
        # Count users registered in this month
        next_month = dt.replace(day=28) + timedelta(days=4)
        next_month = next_month - timedelta(days=next_month.day-1)
        user_count = User.objects.filter(
            date_joined__gte=dt,
            date_joined__lt=next_month
        ).count()
        user_registration_labels.append(label)
        user_registration_data.append(user_count)

    return JsonResponse({
        'sales_labels': sales_labels,
        'sales_data': sales_data,
        'profit_data': profit_data,
        'product_sales_labels': product_sales_labels,
        'product_sales_data': product_sales_data,
        'order_status_labels': order_status_labels,
        'order_status_data': order_status_data,
        'user_registration_labels': user_registration_labels,
        'user_registration_data': user_registration_data,
    })


@staff_member_required
def retry_email_queue_view(request):
    try:
        sent = retry_email_queue()
    except Exception:
        sent = 0
    return JsonResponse({'sent': sent})

# ============================================================================= 
# ADDRESS MANAGEMENT VIEWS
# =============================================================================

from django.core.paginator import Paginator
from django.contrib import messages

@login_required
def user_profile_view(request):
    """User profile with address management and available coupons"""
    # Clear return request session flag after displaying popup
    if 'return_request_submitted' in request.session:
        pass  # Keep for popup

    try:
        addresses = UserAddress.objects.filter(user=request.user)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # === COUPONS ===
        user_coupons = Coupon.objects.filter(user=request.user, is_active=True)
        active_coupons = []
        expired_coupons = []

        for coupon in user_coupons:
            try:
                coupon.remaining_uses_count = coupon.remaining_uses(request.user)
                if not coupon.is_expired() and coupon.remaining_uses_count > 0:
                    active_coupons.append(coupon)
                else:
                    expired_coupons.append(coupon)
            except Exception:
                continue

        used_coupons = Order.objects.filter(
            user=request.user,
            coupon_code__isnull=False
        ).values('coupon_code', 'coupon_discount', 'created_at').order_by('-created_at')[:5]

        # === NOTIFICATIONS ===
        unread_notifications_qs = request.user.notifications.filter(is_read=False).order_by('-created_at')
        notifications_qs = request.user.notifications.order_by('-created_at')

        paginator = Paginator(notifications_qs, 10)
        page = request.GET.get('page')
        notifications_page = paginator.get_page(page)

        # === OTHER DATA ===
        wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')[:4]
        compare_items = Compare.objects.filter(user=request.user).select_related('product')[:4]

        # Expiring soon count
        from django.utils import timezone
        from datetime import timedelta
        expiring_soon_count = 0
        try:
            seven_days_from_now = timezone.now() + timedelta(days=7)
            for coupon in active_coupons:
                if coupon.expiry_date and coupon.expiry_date <= seven_days_from_now:
                    expiring_soon_count += 1
        except Exception:
            expiring_soon_count = 0

        total_savings = sum([float(uc['coupon_discount'] or 0) for uc in used_coupons])

        # Orders (exclude failed payments)
        user_orders = Order.objects.filter(user=request.user).exclude(payment_status='failed').order_by('-created_at')

        # === CONTEXT ===
        context = {
            'addresses': addresses,
            'user': request.user,
            'profile': profile,
            'active_coupons': active_coupons,
            'expired_coupons': expired_coupons,
            'used_coupons': used_coupons,
            'notifications_page': notifications_page,
            'unread_notifications_count': unread_notifications_qs.count(),
            'wishlist_items': wishlist_items,
            'compare_items': compare_items,
            'expiring_soon_count': expiring_soon_count,
            'total_savings': total_savings,
            'orders': user_orders,
        }

        response = render(request, 'user_profile.html', context)

        # Clear session flags
        if 'return_request_submitted' in request.session:
            del request.session['return_request_submitted']
        if 'return_order_number' in request.session:
            del request.session['return_order_number']

        return response

    except Exception as e:
        messages.warning(request, 'Some profile data could not be loaded.')
        return render(request, 'user_profile.html', {
            'addresses': UserAddress.objects.filter(user=request.user),
            'user': request.user,
            'active_coupons': [],
            'expired_coupons': [],
            'used_coupons': [],
            'notifications_page': Paginator(request.user.notifications.none(), 10).get_page(1),
            'unread_notifications_count': 0,
            'wishlist_items': [],
            'compare_items': [],
            'expiring_soon_count': 0,
            'total_savings': 0,
            'orders': Order.objects.filter(user=request.user).exclude(payment_status='failed').order_by('-created_at'),
        })

@login_required 
def add_address_view(request):
    """Add new address"""
    if request.method == 'POST':
        form = UserAddressForm(request.POST)
        if form.is_valid():
            try:
                address = form.save(commit=False)
                address.user = request.user
                address.save()
                messages.success(request, 'Address added successfully!')
                return redirect('user_profile')
            except Exception as e:
                messages.error(request, 'There was an error saving your address. Please try again.')
        else:
            messages.error(request, 'Please fill in all required fields.')
    else:
        form = UserAddressForm()
    
    return render(request, 'add_address.html', {'form': form})

@login_required
def edit_address_view(request, address_id):
    """Edit existing address"""
    try:
        address = UserAddress.objects.get(id=address_id, user=request.user)
    except UserAddress.DoesNotExist:
        messages.error(request, 'Address not found.')
        return redirect('user_profile')
    
    if request.method == 'POST':
        form = UserAddressForm(request.POST, instance=address)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Address updated successfully!')
                return redirect('user_profile')
            except Exception as e:
                messages.error(request, 'There was an error updating your address. Please try again.')
        else:
            messages.error(request, 'Please fill in all required fields.')
    else:
        form = UserAddressForm(instance=address)
    
    return render(request, 'edit_address.html', {'form': form, 'address': address})

@login_required
def delete_address_view(request, address_id):
    """Delete address"""
    try:
        address = UserAddress.objects.get(id=address_id, user=request.user)
        address_info = f"{address.first_name} {address.last_name} - {address.city}, {address.state}"
        address.delete()
        messages.success(request, f'Address "{address_info}" deleted successfully!')
    except UserAddress.DoesNotExist:
        messages.error(request, 'Address not found.')
    
    return redirect('user_profile')

@login_required
def edit_profile_view(request):
    """Edit user profile details"""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('user_profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.title()}: {error}')
    else:
        form = UserProfileForm(instance=request.user)
    
    context = {
        'form': form,
        'user': request.user,
        'profile': UserProfile.objects.get_or_create(user=request.user)[0],
    }
    return render(request, 'edit_profile.html', context)


@login_required
@require_POST
def upload_avatar(request):
    """Upload and save user's profile avatar image from camera or file."""
    try:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        avatar_file = request.FILES.get('avatar')
        if not avatar_file:
            return JsonResponse({'success': False, 'message': 'No file uploaded.'}, status=400)
        # Basic content type check
        if avatar_file.content_type not in ['image/jpeg', 'image/png', 'image/webp']:
            return JsonResponse({'success': False, 'message': 'Unsupported file type.'}, status=400)
        # Assign and save
        profile.avatar = avatar_file
        profile.save()
        return JsonResponse({'success': True, 'url': profile.avatar_url})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Failed to upload avatar.'}, status=500)

@login_required
@require_POST
def remove_avatar(request):
    """Remove the user's profile avatar image."""
    try:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        # Clear the avatar field (file deletion handled by storage backend if configured)
        profile.avatar = None
        profile.save(update_fields=['avatar', 'updated_at'])
        return JsonResponse({'success': True})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Failed to remove avatar.'}, status=500)

@login_required
def set_default_address_view(request, address_id):
    """Set address as default"""
    try:
        address = UserAddress.objects.get(id=address_id, user=request.user)
        # Remove default from other addresses
        UserAddress.objects.filter(user=request.user).update(is_default=False)
        # Set this as default
        address.is_default = True
        address.save()
        messages.success(request, f'Default address set to {address.city}, {address.state}')
    except UserAddress.DoesNotExist:
        messages.error(request, 'Address not found.')
    
    return redirect('user_profile')

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Delete a single notification for the current user"""
    try:
        UserNotification.objects.filter(id=notification_id, user=request.user).delete()
    except Exception:
        pass
    return JsonResponse({'success': True})

@login_required
@require_POST
def mark_all_notifications_read(request):
    """Delete all notifications for the current user"""
    try:
        UserNotification.objects.filter(user=request.user).delete()
    except Exception:
        pass
    return JsonResponse({'success': True})

def create_user_coupon(user, coupon_type, amount, reason):
    """Helper function to create user-specific coupon and notify using new Coupon model"""
    import random
    import string
    from datetime import timedelta
    from django.utils import timezone
    
    # Generate unique coupon code
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not Coupon.objects.filter(code=code).exists():
            break
    
    # Convert coupon_type to match new model
    discount_type = 'percent' if coupon_type == 'percentage' else 'flat'
    
    # Create coupon using new Coupon model
    coupon = Coupon.objects.create(
        user=user,
        code=code,
        discount_type=discount_type,
        discount_value=amount,
        min_order_value=5000,  # Default minimum order
        max_uses_per_user=2,   # Default uses
        expiry_date=timezone.now() + timedelta(days=7),  # Valid for 7 days
        is_active=True
    )
    
    # Create notification
    notification_title = f"New Coupon: {code}"
    if discount_type == 'percent':
        notification_message = f"Congratulations! You've received a {amount}% discount coupon for {reason}. Use code '{code}' at checkout."
    else:
        notification_message = f"Congratulations! You've received a ₹{amount} discount coupon for {reason}. Use code '{code}' at checkout."
    
    UserNotification.objects.create(
        user=user,
        notification_type='coupon_awarded',
        title=notification_title,
        message=notification_message,
        coupon=coupon
    )
    
    return coupon

# =============================================================================
# WISHLIST FUNCTIONALITY
# =============================================================================

@login_required
def toggle_wishlist(request, product_id):
    """Add or remove product from wishlist"""
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found'})
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if created:
        # Added to wishlist
        message = f'{product.name} added to wishlist'
        in_wishlist = True
    else:
        # Remove from wishlist
        wishlist_item.delete()
        message = f'{product.name} removed from wishlist'
        in_wishlist = False
    
    return JsonResponse({
        'success': True,
        'message': message,
        'in_wishlist': in_wishlist,
        'wishlist_count': Wishlist.objects.filter(user=request.user).count()
    })

@login_required
def wishlist_view(request):
    """Display user's wishlist"""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    context = {
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_items.count()
    }
    return render(request, 'wishlist.html', context)

@login_required
def clear_wishlist(request):
    """Clear all items from wishlist"""
    Wishlist.objects.filter(user=request.user).delete()
    return JsonResponse({'success': True, 'message': 'Wishlist cleared successfully'})

# =============================================================================
# COMPARE FUNCTIONALITY
# =============================================================================

@login_required
def toggle_compare(request, product_id):
    """Add or remove product from compare list"""
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found'})
    
    # Limit compare list to 4 items
    compare_count = Compare.objects.filter(user=request.user).count()
    
    compare_item, created = Compare.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if created:
        if compare_count >= 4:
            compare_item.delete()
            return JsonResponse({
                'success': False, 
                'message': 'You can compare maximum 4 products. Remove some products first.'
            })
        
        message = f'{product.name} added to compare list'
        in_compare = True
    else:
        compare_item.delete()
        message = f'{product.name} removed from compare list'
        in_compare = False
    
    return JsonResponse({
        'success': True,
        'message': message,
        'in_compare': in_compare,
        'compare_count': Compare.objects.filter(user=request.user).count()
    })

@login_required
def compare_view(request):
    """Display product comparison page"""
    compare_items = Compare.objects.filter(user=request.user).select_related('product')[:4]
    products = [item.product for item in compare_items]
    
    context = {
        'compare_items': compare_items,
        'products': products,
        'compare_count': len(products)
    }
    return render(request, 'compare.html', context)

@login_required
def clear_compare(request):
    """Clear all items from compare list"""
    Compare.objects.filter(user=request.user).delete()
    return JsonResponse({'success': True, 'message': 'Compare list cleared successfully'})

# =============================================================================
# COUPON FUNCTIONALITY
# =============================================================================

@login_required
def apply_user_coupon(request):
    """Apply a coupon code.
    Supports both user-specific Coupon and global Discount codes.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    coupon_code = (request.POST.get('coupon_code', '') or '').strip()
    if not coupon_code:
        return JsonResponse({'success': False, 'message': 'Please enter a coupon code'})
    
    # Get cart total
    cart_items = Cart.objects.filter(user=request.user)
    if not cart_items.exists():
        return JsonResponse({'success': False, 'message': 'Your cart is empty'})
    subtotal = sum(item.total_price for item in cart_items)
    
    # Try user-specific Coupon first (case-insensitive)
    coupon = Coupon.objects.filter(code__iexact=coupon_code).first()
    if coupon:
        is_valid, error_message = coupon.is_valid(request.user)
        if not is_valid:
            return JsonResponse({'success': False, 'message': error_message})
        if subtotal < coupon.min_order_value:
            return JsonResponse({
                'success': False,
                'message': f'Minimum order value is ₹{coupon.min_order_value}. Current cart value: ₹{subtotal}'
            })
        discount_amount = coupon.get_discount_amount(subtotal)
        new_total = subtotal - discount_amount
        # Store in session
        request.session['applied_coupon_type'] = 'user'
        request.session['applied_coupon_id'] = coupon.id
        request.session['coupon_discount_amount'] = float(discount_amount)
        return JsonResponse({
            'success': True,
            'message': f'Coupon applied successfully! You saved ₹{discount_amount:.2f}',
            'discount_amount': float(discount_amount),
            'new_total': float(new_total),
            'coupon_code': coupon.code
        })
    
    # Fallback: global Discount code
    disc = Discount.objects.filter(code__iexact=coupon_code, active=True).first()
    if not disc:
        return JsonResponse({'success': False, 'message': 'Invalid coupon code'})
    
    is_valid, error_message = disc.is_valid(request.user, order_amount=subtotal)
    if not is_valid:
        return JsonResponse({'success': False, 'message': error_message})
    
    discount_amount = disc.get_discount_amount(subtotal)
    new_total = subtotal - discount_amount
    
    # Store in session
    request.session['applied_coupon_type'] = 'discount'
    request.session['applied_discount_id'] = disc.id
    request.session['coupon_discount_amount'] = float(discount_amount)
    
    return JsonResponse({
        'success': True,
        'message': f'Coupon applied successfully! You saved ₹{discount_amount:.2f}',
        'discount_amount': float(discount_amount),
        'new_total': float(new_total),
        'coupon_code': disc.code
    })

@login_required
def remove_user_coupon(request):
    """Remove any applied coupon (user-specific or global)."""
    for key in ['applied_coupon_id', 'applied_discount_id', 'applied_coupon_type', 'coupon_discount_amount']:
        if key in request.session:
            del request.session[key]
    
    # Calculate new total
    cart_items = Cart.objects.filter(user=request.user)
    subtotal = sum(item.total_price for item in cart_items)
    
    return JsonResponse({
        'success': True,
        'message': 'Coupon removed successfully',
        'new_total': float(subtotal)
    })

# =============================================================================
# ORDER TRACKING FUNCTIONALITY
# =============================================================================

def track_order(request):
    """Order tracking page for customers"""
    from datetime import timedelta
    from django.conf import settings
    
    order = None
    error_message = None
    steps = {}
    steps_time = {}
    estimated_delivery_date = None
    
    # Check for tracking ID in GET params (from invoice link)
    tracking_id_param = request.GET.get('tracking_id', '').strip()
    
    if request.method == 'POST' or tracking_id_param:
        tracking_id = request.POST.get('tracking_id', tracking_id_param).strip()
        
        if not tracking_id:
            error_message = 'Please enter a tracking ID.'
        else:
            try:
                order = Order.objects.get(tracking_id=tracking_id.upper())
                
                # Calculate estimated delivery date
                delivery_days = getattr(settings, 'ORDER_DELIVERY_DAYS', 5)
                estimated_delivery_date = order.created_at + timedelta(days=delivery_days)
                
                # Mark completed steps based on current status
                status_order = ['placed', 'processing', 'dispatched', 'out_for_delivery', 'delivered']
                current_index = status_order.index(order.status) if order.status in status_order else 0
                
                for i, status in enumerate(status_order):
                    steps[status] = i <= current_index
                    if i <= current_index:
                        # Use actual timestamps where available
                        if status == 'delivered' and order.delivered_at:
                            steps_time[status] = order.delivered_at.strftime('%b %d, %Y at %I:%M %p')
                        elif status == 'placed':
                            steps_time[status] = order.created_at.strftime('%b %d, %Y at %I:%M %p')
                        else:
                            steps_time[status] = order.updated_at.strftime('%b %d, %Y at %I:%M %p')
                    else:
                        steps_time[status] = 'Pending'
                
            except Order.DoesNotExist:
                error_message = 'Invalid tracking ID. Please check and try again.'
    
    return render(request, 'track_order.html', {
        'order': order,
        'error_message': error_message,
        'steps': steps,
        'steps_time': steps_time,
        'estimated_delivery_date': estimated_delivery_date
    })

def track_order_ajax(request):
    """AJAX endpoint for order tracking"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    tracking_id = request.POST.get('tracking_id', '').strip()
    
    if not tracking_id:
        return JsonResponse({'success': False, 'message': 'Please enter a tracking ID'})
    
    try:
        order = Order.objects.select_related().prefetch_related('items__product').get(
            tracking_id=tracking_id.upper()
        )
        
        # Prepare order data
        # Step completion flags and timestamps
        status_order = ['placed', 'processing', 'dispatched', 'out_for_delivery', 'delivered']
        current_index = status_order.index(order.status) if order.status in status_order else 0
        steps = {}
        steps_time = {}
        for i, st in enumerate(status_order):
            steps[st] = i <= current_index
            if i <= current_index:
                if st == 'placed':
                    ts = order.created_at
                elif st == 'delivered' and order.delivered_at:
                    ts = order.delivered_at
                else:
                    ts = order.updated_at
                steps_time[st] = ts.strftime('%B %d, %Y at %I:%M %p')
            else:
                steps_time[st] = 'Pending'

        # Estimated delivery date (Order Date + N days)
        try:
            from datetime import timedelta
            from django.conf import settings as dj_settings
            delivery_days = getattr(dj_settings, 'ORDER_DELIVERY_DAYS', 5)
            estimated_delivery_date = (order.created_at + timedelta(days=delivery_days)).strftime('%B %d, %Y')
        except Exception:
            estimated_delivery_date = None

        order_data = {
            'id': order.id,
            'tracking_id': order.tracking_id,
            'order_number': order.order_number,
            'status': order.status,
            'status_display': order.status_display,
            'payment_status': order.payment_status,
            'payment_method': order.get_payment_method_display(),
            'created_at': order.created_at.strftime('%B %d, %Y at %I:%M %p'),
            'updated_at': order.updated_at.strftime('%B %d, %Y at %I:%M %p'),
            'delivered_at': order.delivered_at.strftime('%B %d, %Y at %I:%M %p') if order.delivered_at else None,
            'estimated_delivery_date': estimated_delivery_date,
            'total': str(order.total),
            'subtotal': str(order.subtotal),
            'coupon_discount': str(order.coupon_discount),
            'shipping_name': order.shipping_name,
            'shipping_address': order.shipping_address,
            'email': mask_email(order.email),
            'phone': order.phone[-4:] if order.phone and len(order.phone) > 4 else order.phone,
            'items': [],
            'steps': steps,
            'steps_time': steps_time,
            # Helpful URLs for buttons
            'urls': {
                'invoice': reverse('invoice', args=[order.id]),
            },
            'is_cod': (order.payment_method == 'cash_on_delivery') if hasattr(order, 'payment_method') else (getattr(order, 'payment_method', '') == 'cash_on_delivery')
        }
        
        # Add order items
        for item in order.items.all():
            order_data['items'].append({
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': str(item.price),
                'total': str(item.price * item.quantity),
                'product_image': item.product.image.url if item.product.image else None
            })
        # Add support URL with safe fallback
        try:
            order_data['urls']['support'] = reverse('contact')
        except Exception:
            order_data['urls']['support'] = '/contact/'

        return JsonResponse({
            'success': True,
            'order': order_data
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'message': 'Invalid tracking ID. Please check and try again.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': 'An error occurred while retrieving order information.'
        })

@login_required
def my_orders(request):
    """Display user's order history - ALL orders"""
    # Exclude failed payment orders from listing
    orders = Order.objects.filter(user=request.user).exclude(payment_status='failed').prefetch_related('items__product').order_by('-created_at')

    # ✅ Filter by order status (newly added)
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    # Pagination
    paginator = Paginator(orders, 10)  # Show 10 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'my_orders.html', {
        'page_obj': page_obj,
        'orders': page_obj,
        'status_filter': status_filter
    })

@login_required
def order_detail(request, order_id):
    """Display detailed order information for logged-in user"""
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'), 
        id=order_id, 
        user=request.user
    )
    
    return render(request, 'order_detail.html', {
        'order': order
    })

def get_order_status_progress(status):
    """Helper function to get order status progress for tracking visualization"""
    status_map = {
        'placed': {'step': 1, 'label': 'Order Placed', 'icon': 'fas fa-shopping-cart'},
        'processing': {'step': 2, 'label': 'Processing', 'icon': 'fas fa-cog'},
        'dispatched': {'step': 3, 'label': 'Dispatched', 'icon': 'fas fa-truck'},
        'out_for_delivery': {'step': 4, 'label': 'Out for Delivery', 'icon': 'fas fa-shipping-fast'},
        'delivered': {'step': 5, 'label': 'Delivered', 'icon': 'fas fa-check-circle'},
        'returning': {'step': 6, 'label': 'Returning', 'icon': 'fas fa-undo'},
        'returned': {'step': 7, 'label': 'Returned', 'icon': 'fas fa-undo-alt'},
        'cancelled': {'step': 0, 'label': 'Cancelled', 'icon': 'fas fa-times-circle'}
    }
    
    return status_map.get(status, {'step': 1, 'label': status.title(), 'icon': 'fas fa-question-circle'})

@login_required
def return_order(request, order_id):
    """Display return form for delivered orders within 10 days of delivery"""
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('my_orders')
    
    # Only allow returns for delivered orders
    if order.status != 'delivered':
        messages.error(request, 'Returns are only allowed for delivered orders.')
        return redirect('my_orders')
    
    # Enforce 10-day return window from delivery time
    if not getattr(order, 'can_return', False):
        messages.error(request, 'Return window has expired (10 days from delivery).')
        return redirect('my_orders')
    
    # Check if already returned
    if order.status == 'returning':
        messages.info(request, 'This order is already being returned.')
        return redirect('my_orders')
    
    return render(request, 'return_order.html', {'order': order})

@login_required
@require_POST
def submit_return(request):
    """Submit return request with 10-day window enforcement"""
    order_id = request.POST.get('order_id')
    return_reason = request.POST.get('return_reason', '').strip()
    custom_reason = request.POST.get('custom_reason', '').strip()
    
    if not order_id or not return_reason:
        messages.error(request, 'Please provide a reason for return.')
        return redirect('my_orders')
    
    # If "Other" is selected, use custom reason
    if return_reason == 'Other' and custom_reason:
        return_reason = f"Other: {custom_reason}"
    elif return_reason == 'Other' and not custom_reason:
        messages.error(request, 'Please provide details for your custom reason.')
        return redirect('return_order', order_id=order_id)
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('my_orders')
    
    # Only allow returns for delivered orders
    if order.status != 'delivered':
        messages.error(request, 'Returns are only allowed for delivered orders.')
        return redirect('my_orders')
    
    # Enforce 10-day window
    if not getattr(order, 'can_return', False):
        messages.error(request, 'Return window has expired (10 days from delivery).')
        return redirect('my_orders')
    
    # Update order status to returning
    order.status = 'returning'
    order.return_reason = return_reason
    order.return_requested_at = timezone.now()
    order.save()
    
    # Set session flag for popup
    request.session['return_request_submitted'] = True
    request.session['return_order_number'] = order.order_number
    
    return redirect('user_profile')

# ============================================
# NEW FEATURE: Product Alerts
# ============================================

@login_required
@require_POST
def create_product_alert(request):
    """Create a product alert for price drops or stock availability"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        alert_type = data.get('alert_type')
        target_price = data.get('target_price')
        
        # Validate inputs
        if not product_id or not alert_type:
            return JsonResponse({
                'success': False,
                'message': 'Missing required fields'
            })
        
        # Get product
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Product not found'
            })
        
        # Check if alert already exists
        existing = ProductAlert.objects.filter(
            user=request.user,
            product=product,
            alert_type=alert_type,
            is_active=True
        ).first()
        
        if existing:
            return JsonResponse({
                'success': False,
                'message': 'You already have this alert set up'
            })
        
        # Create new alert
        alert = ProductAlert.objects.create(
            user=request.user,
            product=product,
            alert_type=alert_type,
            target_price=target_price if target_price else None,
            is_active=True
        )
        
        # Send response based on alert type
        messages_map = {
            'price_drop': 'We\'ll notify you when the price drops!',
            'back_in_stock': 'We\'ll notify you when this item is back in stock!',
            'price_target': f'We\'ll notify you when the price drops below ₹{target_price}!'
        }
        
        return JsonResponse({
            'success': True,
            'message': messages_map.get(alert_type, 'Alert created successfully!'),
            'alert_id': alert.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

# ============================================
# ============================================
# FEATURE 5: Gift Registry & Group Purchase
# ============================================

@login_required
def create_registry(request):
    """Create a new gift registry"""
    if request.method == 'POST':
        name = request.POST.get('name')
        registry_type = request.POST.get('registry_type')
        event_date = request.POST.get('event_date')
        description = request.POST.get('description', '')
        
        registry = GiftRegistry.objects.create(
            user=request.user,
            name=name,
            registry_type=registry_type,
            event_date=event_date,
            description=description,
            is_public=True
        )
        messages.success(request, f'Registry "{name}" created successfully!')
        return redirect('view_registry', code=registry.unique_code)
    
    return render(request, 'create_registry.html')

def view_registry(request, code):
    """View a public gift registry"""
    registry = get_object_or_404(GiftRegistry, unique_code=code)
    items = registry.items.select_related('product').all()
    
    return render(request, 'view_registry.html', {
        'registry': registry,
        'items': items,
        'is_owner': request.user == registry.user if request.user.is_authenticated else False
    })

@login_required
def my_registries(request):
    """View user's gift registries"""
    registries = GiftRegistry.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'my_registries.html', {'registries': registries})

# ============================================
# FEATURE 8: Assembly Service Booking
# ============================================

def get_assembly_services(request):
    """Get available assembly services"""
    services = AssemblyService.objects.filter(is_active=True)
    return JsonResponse({
        'services': [
            {
                'id': s.id,
                'name': s.name,
                'description': s.description,
                'base_price': float(s.base_price),
                'price_per_item': float(s.price_per_item),
                'estimated_time': s.estimated_time
            }
            for s in services
        ]
    })

@login_required
@require_POST
def book_assembly_service(request):
    """Book assembly service for an order"""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        service_id = data.get('service_id')
        scheduled_date = data.get('scheduled_date')
        scheduled_time = data.get('scheduled_time')
        
        order = get_object_or_404(Order, id=order_id, user=request.user)
        service = get_object_or_404(AssemblyService, id=service_id)
        
        # Calculate price
        item_count = order.items.count()
        total_price = service.base_price + (service.price_per_item * item_count)
        
        booking = ServiceBooking.objects.create(
            order=order,
            service=service,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            total_price=total_price,
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'booking_id': booking.id,
            'total_price': float(total_price)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

# ============================================
# FEATURE 7: Personalized Recommendations
# ============================================

def get_recommendations(request, product_id):
    """Get product recommendations"""
    product = get_object_or_404(Product, id=product_id)
    
    # Get pre-calculated recommendations
    recommendations = ProductRecommendation.objects.filter(
        product=product
    ).select_related('recommended_product')[:6]
    
    # If no pre-calculated, get similar by category
    if not recommendations:
        similar = Product.objects.filter(
            category=product.category,
            stock__gt=0
        ).exclude(id=product_id)[:6]
        
        return render(request, 'recommendations.html', {
            'product': product,
            'recommendations': similar,
            'reason': 'Similar products in ' + product.category.name
        })
    
    return render(request, 'recommendations.html', {
        'product': product,
        'recommendations': [r.recommended_product for r in recommendations]
    })

@require_POST
def track_product_view(request, product_id):
    """Track product view for recommendations"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.user.is_authenticated:
        UserBrowsingHistory.objects.create(
            user=request.user,
            product=product,
            time_spent=request.POST.get('time_spent', 0)
        )
    else:
        # Track by session
        session_key = request.session.session_key
        if session_key:
            UserBrowsingHistory.objects.create(
                session_key=session_key,
                product=product,
                time_spent=request.POST.get('time_spent', 0)
            )
    
    return JsonResponse({'success': True})

# ============================================
# FEATURE 2: Live Chat Support
# ============================================

@login_required
def chat_view(request):
    """Live chat interface"""
    # Get or create conversation for user
    conversation, created = ChatConversation.objects.get_or_create(
        user=request.user,
        status='active',
        defaults={'subject': 'Customer Support'}
    )
    
    messages = conversation.messages.all()
    
    return render(request, 'chat.html', {
        'conversation': conversation,
        'messages': messages
    })

@login_required
@require_POST
def send_chat_message(request):
    """Send a chat message"""
    try:
        data = json.loads(request.body)
        conversation_id = data.get('conversation_id')
        message_text = data.get('message')
        
        conversation = get_object_or_404(ChatConversation, id=conversation_id, user=request.user)
        
        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            message=message_text,
            is_bot=False,
            is_staff=False
        )
        
        # Simple bot responses
        bot_response = get_bot_response(message_text, user=request.user)
        if bot_response:
            ChatMessage.objects.create(
                conversation=conversation,
                message=bot_response,
                is_bot=True
            )
        
        return JsonResponse({
            'success': True,
            'message_id': message.id
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

def get_bot_response(message, user=None):
    """Rule-based intents + FAQ search (no external API)."""
    from django.db.models import Q
    from .models import Order, FAQ

    text = (message or '').strip()
    q = text.lower()

    # 1) Order status (if logged in) - specific intent that requires user context
    if any(w in q for w in ['order status', 'where is my order', 'track order', 'my order', 'order update']):
        if user and getattr(user, 'is_authenticated', False):
            latest = Order.objects.filter(user=user).order_by('-created_at').first()
            if latest:
                return f"Your latest order #{latest.id} is currently '{latest.status_display}'. Total ₹{latest.total}. You can view details in My Orders."
            else:
                return "I couldn't find any orders on your account yet."
        else:
            return "Please login to check your order status in My Orders."

    # 2) FAQ search (active only) - prioritize exact matches, then partial matches
    if q:
        # First: Try exact question match (case-insensitive)
        exact_match = FAQ.objects.filter(is_active=True, question__iexact=text).first()
        if exact_match:
            return exact_match.answer
        
        # Second: Try full text match in question or tags
        full_match = FAQ.objects.filter(is_active=True).filter(
            Q(question__icontains=text) | Q(tags__icontains=text)
        ).order_by('-updated_at').first()
        if full_match:
            return full_match.answer
        
        # Third: Try matching individual terms (3+ chars) with scoring
        terms = [t for t in q.replace('?', '').replace(',', ' ').split() if len(t) > 2]
        if terms:
            # Build query that matches any term
            term_query = Q()
            for t in terms:
                term_query |= Q(question__icontains=t) | Q(tags__icontains=t)
            
            # Get all matching FAQs and score them
            matching_faqs = FAQ.objects.filter(is_active=True).filter(term_query)
            
            if matching_faqs.exists():
                # Score each FAQ by number of matching terms
                best_faq = None
                best_score = 0
                
                for faq in matching_faqs:
                    score = 0
                    faq_text = (faq.question + ' ' + faq.tags).lower()
                    for term in terms:
                        if term in faq_text:
                            score += 1
                    
                    if score > best_score:
                        best_score = score
                        best_faq = faq
                
                if best_faq and best_score > 0:
                    return best_faq.answer

    # 3) Fallback
    return "Thanks! I couldn't match that. You can ask about orders, returns, shipping, payments, or coupons."
@require_POST
def chatbot_response(request):
    """API endpoint for chatbot responses using FAQ database"""
    try:
        data = json.loads(request.body or '{}')
        message = data.get('message', '').strip()
        
        if not message:
            return JsonResponse({'success': False, 'message': 'No message provided.'}, status=400)
        
        # Get bot response using the FAQ database
        response = get_bot_response(message, user=request.user if request.user.is_authenticated else None)
        
        return JsonResponse({
            'success': True,
            'response': response
        })
    except Exception as e:
        logger.exception('Chatbot response error')
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@require_POST
@login_required
def create_back_in_stock_alert(request):
    import json
    data = json.loads(request.body or '{}')
    product_id = data.get('product_id')
    if not product_id:
        return JsonResponse({'success': False, 'message': 'No product specified.'}, status=400)
    from .models import Product
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found.'}, status=404)
    alert, created = BackInStockAlert.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={"is_active": True, "notified": False}
    )
    if not created:
        # Already requested
        return JsonResponse({'success': False, 'message': 'You already have a back-in-stock alert for this product.'})
    return JsonResponse({'success': True, 'message': 'You will be notified in your profile when this item is back in stock.'})
