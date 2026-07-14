from django.contrib import admin
from django.utils.html import format_html
from django.contrib.admin import SimpleListFilter
from django.urls import reverse, path
from django.shortcuts import render, redirect
from django import forms
from django.conf import settings as dj_settings
from decimal import Decimal, InvalidOperation
from django.db import models as dj_models
import csv, io, os
from django.core.files import File
from .models import (Category, Product, Order, OrderItem, Discount, Review, Contact, UserAddress,
                     UserNotification, Coupon, UserCoupon, Wishlist, Compare,
                     ChatConversation, ChatMessage,
                     ProductDimension, FAQ, StockManagement, VendorPayment, Vendor)
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .utils_sms import send_sms
import logging
from django.db import transaction
from .models import UserActivity

admin.site.site_header = "Furnex Admin"
admin.site.site_title = "Furnex Admin"
admin.site.index_title = "Administration"
logger = logging.getLogger(__name__)

class ProductCSVImportForm(forms.Form):
    csv_file = forms.FileField(help_text='Upload a CSV file with headers: name,category,price,discount_price,stock,description,image(optional)')

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name_title', 'category_title', 'price', 'discount_price', 'stock', 'length', 'height', 'width', 'display_image', 'id')
    list_filter = ('category',)
    search_fields = ('name', 'description')
    readonly_fields = ('display_image',)
    fields = ('name', 'category', 'price', 'discount_price', 'stock', 'description', 'image', 'length', 'height', 'width')
    ordering = ('-id',)  # Show newest products first in admin (higher ID = newer)
    change_list_template = 'admin/core/product/change_list.html'

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True

    # Query optimizations & UX for large FKs
    list_select_related = ('category',)
    autocomplete_fields = ['category']

    # Bigger textarea for text fields
    formfield_overrides = {
        dj_models.TextField: {"widget": forms.Textarea(attrs={"rows": 6, "cols": 80})}
    }
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category').order_by('-id')
    
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='product_import_csv'),
        ]
        return custom + urls

    def import_csv(self, request):
        if not request.user.has_perm('core.add_product'):
            self.message_user(request, 'You do not have permission to import products.', level='error')
            return redirect('..')
        context = dict(
            self.admin_site.each_context(request),
            form=ProductCSVImportForm(),
            title='Import Products from CSV'
        )
        if request.method == 'POST':
            form = ProductCSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                f = form.cleaned_data['csv_file']
                try:
                    decoded = io.TextIOWrapper(f.file, encoding='utf-8-sig')
                    reader = csv.DictReader(decoded)
                except Exception as e:
                    logger.exception('Failed to read CSV')
                    self.message_user(request, f'Failed to read CSV: {e}', level='error')
                    return render(request, 'admin/core/product/import.html', context)

                # Validate headers up front
                expected_headers = {'name','category','price','discount_price','stock','description','image'}
                csv_headers = set([h.strip() for h in reader.fieldnames or []])
                header_missing = expected_headers - csv_headers
                if header_missing:
                    self.message_user(request, f"CSV missing headers: {', '.join(sorted(header_missing))}", level='error')
                    return render(request, 'admin/core/product/import.html', context)

                is_dry_run = request.GET.get('dry_run') in ('1','true','True')

                row_errors = []
                to_create = []
                to_update = []
                update_fields = ['category','price','discount_price','stock','description']
                image_assignments = []  # (product_instance, abs_path)

                # Prefetch categories and existing products by name for quick lookup
                existing_products = {p.name: p for p in Product.objects.all().only('id','name','category','price','discount_price','stock','description')}
                categories = {c.name: c for c in Category.objects.all().only('id','name')}

                for idx, row in enumerate(reader, start=2):  # header is row 1
                    try:
                        name = (row.get('name') or '').strip()
                        category_name = (row.get('category') or '').strip()
                        price_raw = (row.get('price') or '').strip()
                        discount_raw = (row.get('discount_price') or '').strip()
                        stock_raw = (row.get('stock') or '0').strip()
                        description = row.get('description') or ''
                        image_path = (row.get('image') or '').strip()

                        if not name or not category_name or not price_raw:
                            row_errors.append((idx, 'Missing required field(s)'))
                            continue
                        try:
                            price = Decimal(price_raw)
                        except InvalidOperation:
                            row_errors.append((idx, f'Invalid price: {price_raw}'))
                            continue
                        discount_price = None
                        if discount_raw:
                            try:
                                discount_price = Decimal(discount_raw)
                            except InvalidOperation:
                                row_errors.append((idx, f'Invalid discount_price: {discount_raw}'))
                                discount_price = None
                        try:
                            stock = int(stock_raw)
                        except Exception:
                            row_errors.append((idx, f'Invalid stock: {stock_raw}; defaulting to 0'))
                            stock = 0

                        category = categories.get(category_name)
                        if not category:
                            category, _ = Category.objects.get_or_create(name=category_name)
                            categories[category_name] = category

                        existing = existing_products.get(name)
                        if existing:
                            existing.category = category
                            existing.price = price
                            existing.discount_price = discount_price
                            existing.stock = stock
                            existing.description = description
                            to_update.append(existing)
                        else:
                            new_p = Product(
                                name=name,
                                category=category,
                                price=price,
                                discount_price=discount_price,
                                stock=stock,
                                description=description,
                            )
                            to_create.append(new_p)
                            existing_products[name] = new_p  # so subsequent rows treat it as existing

                        # Prepare local image assignment if present
                        if image_path:
                            abs_path = image_path
                            if not os.path.isabs(abs_path):
                                abs_path = os.path.join(dj_settings.MEDIA_ROOT, image_path)
                            if os.path.exists(abs_path):
                                image_assignments.append((name, abs_path))
                            else:
                                row_errors.append((idx, f'Image path not found: {image_path}'))
                    except Exception as e:
                        logger.exception('Row processing failed at line %s', idx)
                        row_errors.append((idx, str(e)))

                created = len(to_create)
                updated = len(to_update)

                # Perform DB writes inside a single atomic transaction
                with transaction.atomic():
                    try:
                        if to_create:
                            Product.objects.bulk_create(to_create, batch_size=500)
                        if to_update:
                            Product.objects.bulk_update(to_update, update_fields, batch_size=500)

                        # Handle images individually after bulk ops (cannot bulk set FileField)
                        if image_assignments:
                            name_to_obj = {p.name: p for p in Product.objects.filter(name__in=[n for n,_ in image_assignments])}
                            for name, abs_path in image_assignments:
                                p = name_to_obj.get(name)
                                if p and os.path.exists(abs_path):
                                    try:
                                        with open(abs_path, 'rb') as imgf:
                                            p.image.save(os.path.basename(abs_path), File(imgf), save=True)
                                    except Exception:
                                        logger.exception('Failed to assign image for %s', name)
                                        row_errors.append((None, f'Failed to assign image for {name}'))

                        if is_dry_run:
                            transaction.set_rollback(True)
                    except Exception:
                        logger.exception('CSV import transaction failed')
                        if not is_dry_run:
                            raise

                # Report results
                sample_errors = ", ".join([f"row {r}: {m}" if r else m for r,m in row_errors[:5]])
                msg = f'Import finished. Created: {created}, Updated: {updated}, Errors: {len(row_errors)}'
                if is_dry_run:
                    msg = '[DRY RUN] ' + msg
                if sample_errors:
                    msg += f'. Sample errors: {sample_errors}'
                self.message_user(request, msg)
                return redirect('..')
            else:
                context['form'] = form
        return render(request, 'admin/core/product/import.html', context)
    
    def display_image(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.image.url)
        return 'No Image'
    
    display_image.short_description = 'Image Preview'

    @admin.display(description="Name")
    def name_title(self, obj):
        return obj.name.title() if obj.name else ''
    @admin.display(description="Category")
    def category_title(self, obj):
        return obj.category.name.title() if obj.category and obj.category.name else ''

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name_title',)

    @admin.display(description="Name")
    def name_title(self, obj):
        return obj.name.title() if obj.name else ''

class FAQCSVImportForm(forms.Form):
    csv_file = forms.FileField(help_text='Upload CSV with headers: question,answer,tags,is_active(optional)')

class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('question', 'answer', 'tags')
    ordering = ('-updated_at',)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='faq_import_csv'),
        ]
        return custom + urls

    def import_csv(self, request):
        if not request.user.has_perm('core.add_faq'):
            self.message_user(request, 'You do not have permission to import FAQs.', level='error')
            return redirect('..')
        context = dict(
            self.admin_site.each_context(request),
            form=FAQCSVImportForm(),
            title='Import FAQs from CSV'
        )
        if request.method == 'POST':
            form = FAQCSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                f = form.cleaned_data['csv_file']
                try:
                    decoded = io.TextIOWrapper(f.file, encoding='utf-8-sig')
                    reader = csv.DictReader(decoded)
                except Exception as e:
                    logger.exception('Failed to read CSV (FAQ)')
                    self.message_user(request, f'Failed to read CSV: {e}', level='error')
                    return render(request, 'admin/core/product/import.html', context)

                expected_headers = {'question','answer','tags','is_active'}
                csv_headers = set([h.strip() for h in reader.fieldnames or []])
                if not {'question','answer'}.issubset(csv_headers):
                    self.message_user(request, 'CSV must include at least headers: question, answer', level='error')
                    return render(request, 'admin/core/product/import.html', context)

                created = 0
                updated = 0
                row_errors = []
                to_create = []

                for idx, row in enumerate(reader, start=2):
                    try:
                        q = (row.get('question') or '').strip()
                        a = (row.get('answer') or '').strip()
                        t = (row.get('tags') or '').strip()
                        active_raw = (row.get('is_active') or '').strip().lower()
                        active = True if active_raw in ('1','true','yes','y') else False if active_raw in ('0','false','no','n') else True
                        if not q or not a:
                            row_errors.append((idx, 'Missing question or answer'))
                            continue
                        to_create.append(FAQ(question=q, answer=a, tags=t, is_active=active))
                    except Exception as e:
                        logger.exception('FAQ row failed at %s', idx)
                        row_errors.append((idx, str(e)))

                if to_create:
                    FAQ.objects.bulk_create(to_create, batch_size=500)
                    created = len(to_create)

                sample_errors = ", ".join([f"row {r}: {m}" for r,m in row_errors[:5]])
                msg = f'FAQs import finished. Created: {created}, Errors: {len(row_errors)}'
                if sample_errors:
                    msg += f'. Sample errors: {sample_errors}'
                self.message_user(request, msg)
                return redirect('..')
            else:
                context['form'] = form
        # Reuse the generic product import template that renders a file form nicely
        return render(request, 'admin/core/product/import.html', context)

admin.site.register(FAQ, FAQAdmin)

admin.site.register(Product, ProductAdmin)
# Custom filter for return requests
class ReturnRequestFilter(SimpleListFilter):
    title = 'Return Status'
    parameter_name = 'return_status'
    
    def lookups(self, request, model_admin):
        return (
            ('pending', 'Pending Returns'),
            ('approved', 'Approved Returns'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(status='returning')
        if self.value() == 'approved':
            return queryset.filter(status='returned')

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'tracking_id', 'first_name', 'last_name', 'status', 'payment_status', 'payment_method', 'total', 'return_reason_display', 'created_at', 'invoice_link')
    list_filter = ('status', 'payment_method', 'payment_status', ReturnRequestFilter, 'created_at')
    search_fields = ('tracking_id', 'first_name', 'last_name', 'email', 'phone', 'id', 'return_reason')
    readonly_fields = ('tracking_id', 'created_at', 'updated_at', 'return_requested_at', 'return_reason')
    list_editable = ('status',)
    actions = ['mark_as_processing', 'mark_as_dispatched', 'mark_as_out_for_delivery', 'mark_as_delivered', 'approve_return_request', 'reject_return_request']
    date_hierarchy = 'created_at'

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True
    
    fieldsets = (
        ('Order Information', {
            'fields': ('tracking_id', 'status', 'payment_status', 'payment_method', 'created_at', 'updated_at')
        }),
        ('Return Information', {
            'fields': ('return_reason', 'return_requested_at'),
            'classes': ('collapse',),
        }),
        ('Customer Details', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'company_name')
        }),
        ('Billing Address', {
            'fields': ('address', 'apartment', 'state_country', 'postal_zip', 'country')
        }),
        ('Shipping Address', {
            'fields': ('ship_to_different', 'ship_first_name', 'ship_last_name', 'ship_address', 'ship_apartment', 'ship_state_country', 'ship_postal_zip', 'ship_country')
        }),
        ('Order Details', {
            'fields': ('subtotal', 'coupon_code', 'coupon_discount', 'total', 'order_notes')
        }),
        ('Payment Information', {
            'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')
        })
    )
    
    def _log_change(self, request, obj, message):
        try:
            self.log_change(request, obj, message)
        except Exception:
            logger.debug('Admin log_change failed for %s', obj.pk)

    def mark_as_processing(self, request, queryset):
        updated = 0
        with transaction.atomic():
            for order in queryset.select_for_update():
                order.status = 'processing'
                order.save(update_fields=['status'])
                updated += 1
                self._log_change(request, order, 'Marked as Processing via action')
        self.message_user(request, f'{updated} orders marked as Processing.')
    mark_as_processing.short_description = "Mark selected orders as Processing"
    
    def mark_as_dispatched(self, request, queryset):
        updated = 0
        with transaction.atomic():
            for order in queryset.select_for_update():
                order.status = 'dispatched'
                order.save(update_fields=['status'])
                updated += 1
                self._log_change(request, order, 'Marked as Dispatched via action')
        self.message_user(request, f'{updated} orders marked as Dispatched.')
    mark_as_dispatched.short_description = "Mark selected orders as Dispatched"
    
    def mark_as_out_for_delivery(self, request, queryset):
        updated = 0
        with transaction.atomic():
            for order in queryset.select_for_update():
                order.status = 'out_for_delivery'
                order.save(update_fields=['status'])
                updated += 1
                self._log_change(request, order, 'Marked as Out for Delivery via action')
        self.message_user(request, f'{updated} orders marked as Out for Delivery.')
    mark_as_out_for_delivery.short_description = "Mark selected orders as Out for Delivery"
    
    def mark_as_delivered(self, request, queryset):
        updated = 0
        with transaction.atomic():
            for order in queryset.select_for_update():
                order.status = 'delivered'
                order.delivered_at = timezone.now()
                order.save(update_fields=['status', 'delivered_at'])
                updated += 1
                self._log_change(request, order, 'Marked as Delivered via action')
        self.message_user(request, f'{updated} orders marked as Delivered.')
    mark_as_delivered.short_description = "Mark selected orders as Delivered"
    
    def approve_return_request(self, request, queryset):
        """Approve return and refund payment"""
        updated = 0
        with transaction.atomic():
            for order in queryset.select_for_update().filter(status='returning'):
                order.status = 'returned'
                order.payment_status = 'refunded'
                order.save(update_fields=['status','payment_status'])
                updated += 1
                self._log_change(request, order, 'Return approved & payment refunded')
                # Send notification email
                try:
                    send_mail(
                        subject=f'Return Approved - Order #{order.order_number}',
                        message=f'Your return request for Order #{order.order_number} has been approved. Payment will be refunded within 5-7 business days.',
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[order.email],
                        fail_silently=True
                    )
                except Exception:
                    logger.exception('Email send failed for approve_return_request order=%s', order.pk)
        self.message_user(request, f'{updated} return requests approved and marked as Refunded.')
    approve_return_request.short_description = "✅ Approve Return & Refund Payment"
    
    def reject_return_request(self, request, queryset):
        """Reject return request and revert to delivered"""
        updated = 0
        with transaction.atomic():
            for order in queryset.select_for_update().filter(status='returning'):
                order.status = 'delivered'
                order.return_reason = None
                order.save(update_fields=['status','return_reason'])
                updated += 1
                self._log_change(request, order, 'Return request rejected')
        self.message_user(request, f'{updated} return requests rejected.')
    reject_return_request.short_description = "❌ Reject Return Request"
    
    def return_reason_display(self, obj):
        """Display return reason with badge"""
        if obj.return_reason:
            return format_html(
                '<span style="background: #fef3c7; color: #92400e; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
                obj.return_reason[:50] + '...' if len(obj.return_reason) > 50 else obj.return_reason
            )
        return '-'
    return_reason_display.short_description = 'Return Reason'

    def save_model(self, request, obj, form, change):
        previous_status = None
        if obj.pk:
            try:
                previous_status = Order.objects.get(pk=obj.pk).status
            except Order.DoesNotExist:
                previous_status = None
        super().save_model(request, obj, form, change)
        # Notify customer on status change
        if previous_status and previous_status != obj.status:
            try:
                html = render_to_string('registration_email_order.html', {
                    'order': obj,
                    'eta_date': (obj.created_at + timezone.timedelta(days=getattr(settings, 'ORDER_DELIVERY_DAYS', 5))).date(),
                    'site_url': request.build_absolute_uri('/')[:-1],
                    'cod_fee': settings.COD_EXTRA_FEE if obj.payment_method == 'cash_on_delivery' else 0,
                })
                send_mail(
                    subject=f'Your Order #{obj.id} is now {obj.status.capitalize()}',
                    message=f'Your order #{obj.id} status changed to {obj.status}.',
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[obj.email],
                    html_message=html,
                    fail_silently=True
                )
                # SMS notify if phone present
                if obj.phone:
                    try:
                        send_sms(obj.phone, f'Furnex: Your order #{obj.id} is now {obj.status}.')
                    except Exception:
                        logger.exception('SMS send failed for order=%s', obj.pk)
            except Exception:
                logger.exception('Email template/send failed for order=%s', obj.pk)

    def invoice_link(self, obj):
        url = reverse('admin_invoice', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">Invoice</a>', url)
    invoice_link.short_description = 'Invoice'

admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem)
# Custom admin forms to correctly handle datetime-local inputs without SplitDateTime errors
class DiscountAdminForm(forms.ModelForm):
    valid_from = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M']
    )
    valid_until = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M']
    )

    class Meta:
        model = Discount
        fields = '__all__'

@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    form = DiscountAdminForm
class RatingFilter(SimpleListFilter):
    title = 'rating'
    parameter_name = 'rating'

    def lookups(self, request, model_admin):
        return [(str(n), f'{n} stars') for n in [5,4,3,2,1]]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            try:
                return queryset.filter(rating=int(value))
            except Exception:
                return queryset
        return queryset


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product_title', 'rating', 'user_title', 'name_title', 'approved', 'created_at')
    list_filter = ('approved', RatingFilter, 'product')
    search_fields = ('product__name','user__username','name','comment')
    list_editable = ('approved',)

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True

    list_select_related = ('product','user')
    autocomplete_fields = ['product','user']

    # Bigger textarea for text fields
    formfield_overrides = {
        dj_models.TextField: {"widget": forms.Textarea(attrs={"rows": 6, "cols": 80})}
    }
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product','user').order_by('-created_at')

    @admin.display(description="Product")
    def product_title(self, obj):
        return obj.product.name.title() if obj.product and obj.product.name else ''
    @admin.display(description="User")
    def user_title(self, obj):
        return obj.user.username.title() if obj.user and obj.user.username else ''
    @admin.display(description="Name")
    def name_title(self, obj):
        return obj.name.title() if obj.name else ''

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('first_name_title', 'last_name_title', 'email', 'message_preview', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'message')
    list_editable = ('is_read',)
    readonly_fields = ('created_at',)
    
    def message_preview(self, obj):
        """Show first 50 characters of message"""
        if len(obj.message) > 50:
            return obj.message[:50] + "..."
        return obj.message
    message_preview.short_description = 'Message Preview'

    @admin.display(description="First name")
    def first_name_title(self, obj):
        return obj.first_name.title() if obj.first_name else ''
    @admin.display(description="Last name")
    def last_name_title(self, obj):
        return obj.last_name.title() if obj.last_name else ''

@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = (
        'user_titlecase', 'first_name_titlecase', 'last_name_titlecase',
        'city_titlecase', 'state_titlecase', 'postal_code', 'country_titlecase',
        'address_type_titlecase', 'phone', 'is_default', 'created_at'
    )
    list_filter = ('address_type', 'is_default', 'country', 'state', 'city', 'created_at')
    search_fields = ('user__username', 'user__email', 'first_name', 'last_name', 'city', 'state', 'postal_code', 'address', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True
    list_select_related = ('user',)
    autocomplete_fields = ['user']
    fieldsets = (
        ('User', {'fields': ('user', 'address_type', 'is_default')}),
        ('Name', {'fields': ('first_name', 'last_name', 'company')}),
        ('Address', {'fields': ('address', 'apartment', 'city', 'state', 'postal_code', 'country')}),
        ('Contact', {'fields': ('phone',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').order_by('-created_at')
    @admin.display(description="User")
    def user_titlecase(self, obj):
        return obj.user.get_full_name().title() if obj.user.get_full_name() else obj.user.username.title()
    @admin.display(description="First name")
    def first_name_titlecase(self, obj):
        return obj.first_name.title() if obj.first_name else ''
    @admin.display(description="Last name")
    def last_name_titlecase(self, obj):
        return obj.last_name.title() if obj.last_name else ''
    @admin.display(description="City")
    def city_titlecase(self, obj):
        return obj.city.title() if obj.city else ''
    @admin.display(description="State")
    def state_titlecase(self, obj):
        return obj.state.title() if obj.state else ''
    @admin.display(description="Country")
    def country_titlecase(self, obj):
        return obj.country.title() if obj.country else ''
    @admin.display(description="Address type")
    def address_type_titlecase(self, obj):
        return obj.address_type.title() if obj.address_type else ''

class UserAddressInline(admin.StackedInline):
    model = UserAddress
    extra = 0
    fields = ('address_type', 'is_default', 'first_name', 'last_name', 'company', 'phone', 'address', 'apartment', 'city', 'state', 'postal_code', 'country')
    show_change_link = True

# Extend the built-in User admin to include addresses inline
try:
    admin.site.unregister(User)
except Exception:
    pass

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [UserAddressInline]

@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    # Hide this model entirely from admin UI
    def get_model_perms(self, request):
        return {}
    def has_view_permission(self, request, obj=None):
        return False
    def get_queryset(self, request):
        return super().get_queryset(request).none()

@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    # Hide this model entirely from admin UI
    def get_model_perms(self, request):
        return {}
    def has_view_permission(self, request, obj=None):
        return False
    def get_queryset(self, request):
        return super().get_queryset(request).none()

class CouponAdminForm(forms.ModelForm):
    expiry_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M']
    )

    class Meta:
        model = Coupon
        fields = '__all__'

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    form = CouponAdminForm
    list_display = ('code_upper', 'user_title', 'discount_type', 'discount_value', 'min_order_value', 'max_uses_per_user', 'expiry_date', 'is_active', 'created_at')
    list_filter = ('discount_type', 'is_active', 'expiry_date', 'created_at')
    search_fields = ('code', 'user__username', 'user__email')
    list_editable = ('is_active',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'expiry_date'

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True

    list_select_related = ('user',)
    autocomplete_fields = ['user']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').order_by('-created_at')

    @admin.display(description="Code")
    def code_upper(self, obj):
        return obj.code.upper() if obj.code else ''
    @admin.display(description="User")
    def user_title(self, obj):
        return obj.user.username.title() if obj.user and obj.user.username else ''

@admin.register(UserCoupon)
class UserCouponAdmin(admin.ModelAdmin):
    list_display = ('user', 'coupon', 'order', 'discount_applied', 'used_at')
    list_filter = ('used_at', 'discount_applied')
    search_fields = ('user__username', 'coupon__code', 'order__id')
    readonly_fields = ('used_at',)
    date_hierarchy = 'used_at'

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True

    list_select_related = ('user','coupon','order')
    autocomplete_fields = ['user','coupon','order']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'coupon', 'order').order_by('-used_at')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user_title', 'product_title', 'added_at')
    list_filter = ('added_at', 'product__category')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('added_at',)

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True

    list_select_related = ('user','product')
    autocomplete_fields = ['user','product']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product').order_by('-added_at')

    @admin.display(description="User")
    def user_title(self, obj):
        return obj.user.username.title() if obj.user and obj.user.username else ''
    @admin.display(description="Product")
    def product_title(self, obj):
        return obj.product.name.title() if obj.product and obj.product.name else ''

@admin.register(Compare)
class CompareAdmin(admin.ModelAdmin):
    list_display = ('user_title', 'product_title', 'added_at')
    list_filter = ('added_at', 'product__category')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('added_at',)

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True

    list_select_related = ('user','product')
    autocomplete_fields = ['user','product']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product').order_by('-added_at')

    @admin.display(description="User")
    def user_title(self, obj):
        return obj.user.username.title() if obj.user and obj.user.username else ''
    @admin.display(description="Product")
    def product_title(self, obj):
        return obj.product.name.title() if obj.product and obj.product.name else ''

# ============================================
# ADMIN FOR NEW FEATURES
# ============================================

# Feature 1: Live Chat Support
class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('sender', 'is_bot', 'is_staff', 'message', 'is_read', 'created_at')

@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_title', 'assigned_to_title', 'status_title', 'subject_title', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('user__username', 'session_key', 'subject')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['user', 'assigned_to']
    inlines = [ChatMessageInline]
    
    def user_display(self, obj):
        if obj.user:
            return obj.user.username
        return f"Guest ({obj.session_key[:8]}...)"
    user_display.short_description = 'User'

    @admin.display(description="User")
    def user_title(self, obj):
        return obj.user.username.title() if obj.user and obj.user.username else (f"Guest ({obj.session_key[:8]}...)")
    @admin.display(description="Assigned To")
    def assigned_to_title(self, obj):
        return obj.assigned_to.username.title() if obj.assigned_to and obj.assigned_to.username else ''
    @admin.display(description="Status")
    def status_title(self, obj):
        return obj.get_status_display().title() if hasattr(obj, 'get_status_display') and obj.status else ''
    @admin.display(description="Subject")
    def subject_title(self, obj):
        return obj.subject.title() if obj.subject else ''

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender_display', 'is_bot', 'is_staff', 'message_preview', 'is_read', 'created_at')
    list_filter = ('is_bot', 'is_staff', 'is_read', 'created_at')
    search_fields = ('message', 'conversation__id')
    readonly_fields = ('created_at',)
    
    @admin.display(description="Sender")
    def sender_display(self, obj):
        if obj.is_bot:
            return 'Bot'
        return obj.sender.username.title() if obj.sender and obj.sender.username else 'Guest'
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

# Feature 3: Smart Size/Dimension Filter
@admin.register(ProductDimension)
class ProductDimensionAdmin(admin.ModelAdmin):
    list_display = ('product_title', 'width', 'height', 'depth', 'weight', 'seating_capacity', 'material_title', 'assembly_required')
    list_filter = ('assembly_required', 'material')
    search_fields = ('product__name', 'material')
    autocomplete_fields = ['product']

    @admin.display(description="Product")
    def product_title(self, obj):
        return obj.product.name.title() if obj.product and obj.product.name else ''
    @admin.display(description="Material")
    def material_title(self, obj):
        return obj.material.title() if obj.material else ''

# ============================================
# ADMIN FOR STOCK MANAGEMENT AND VENDOR PAYMENT
# ============================================


@admin.register(StockManagement)
class StockManagementAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'product_category', 'product_price', 'product_quantity', 'length', 'height', 'width', 'total_price', 'purchase_date', 'deploy_action')
    list_filter = ('product_category', 'purchase_date')
    search_fields = ('product_name', 'product_category__name')
    readonly_fields = ('total_price', 'purchase_date')
    date_hierarchy = 'purchase_date'

    # Admin UX defaults
    list_per_page = 100
    actions_on_top = True
    actions_selection_counter = True
    preserve_filters = True

    list_select_related = ('product_category',)
    autocomplete_fields = ['product_category']

    fieldsets = (
        ('Product Details', {
            'fields': ('product_category', 'product_name', 'product_price', 'product_quantity')
        }),
        ('Product Dimensions', {
            'fields': ('length', 'height', 'width')
        }),
        ('Purchase Summary', {
            'fields': ('total_price', 'purchase_date')
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product_category').order_by('-purchase_date')

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/deploy/', self.admin_site.admin_view(self.deploy_view), name='stockmanagement_deploy'),
        ]
        return custom + urls

    def deploy_action(self, obj):
        url = reverse('admin:stockmanagement_deploy', args=[obj.pk])
        return format_html('<a class="button" href="{}">Deploy</a>', url)
    deploy_action.short_description = 'Deploy to Product'

    class DeployForm(forms.Form):
        deploy_quantity = forms.IntegerField(min_value=1, label='Quantity to deploy')

    @transaction.atomic
    def deploy_view(self, request, pk):
        stock = StockManagement.objects.select_for_update().get(pk=pk)
        FormClass = self.DeployForm
        initial = {'deploy_quantity': stock.current_stock}
        if request.method == 'POST':
            form = FormClass(request.POST)
            if form.is_valid():
                qty = form.cleaned_data['deploy_quantity']
                if qty <= 0 or qty > stock.current_stock:
                    form.add_error('deploy_quantity', 'Quantity must be between 1 and current stock')
                else:
                    category = stock.product_category
                    product, created = Product.objects.get_or_create(
                        name=stock.product_name,
                        category=category,
                        defaults={
                            'price': stock.product_price,
                            'stock': 0,
                            'length': stock.length,
                            'height': stock.height,
                            'width': stock.width
                        }
                    )
                    if created and stock.product_price:
                        product.price = stock.product_price
                    # Update dimensions if they exist in stock and not already set in product
                    if stock.length and not product.length:
                        product.length = stock.length
                    if stock.height and not product.height:
                        product.height = stock.height
                    if stock.width and not product.width:
                        product.width = stock.width
                    product.stock = (product.stock or 0) + qty
                    product.save()

                    # Decrement stock management quantities and recalc total
                    stock.current_stock = stock.current_stock - qty
                    new_product_quantity = max(0, stock.product_quantity - qty)
                    stock.product_quantity = new_product_quantity
                    stock.total_price = stock.product_price * stock.product_quantity
                    if stock.current_stock <= 0 or stock.product_quantity <= 0:
                        stock.delete()
                    else:
                        if not stock.product:
                            stock.product = product
                        stock.save(update_fields=['current_stock', 'product_quantity', 'total_price', 'product'])

                    return redirect(reverse('admin:core_product_change', args=[product.pk]))
        else:
            form = FormClass(initial=initial)

        context = dict(
            self.admin_site.each_context(request),
            title=f'Deploy stock for {stock.product_name}',
            form=form,
            stock=stock,
        )
        return render(request, 'admin/core/stockmanagement/deploy.html', context)

@admin.register(VendorPayment)
class VendorPaymentAdmin(admin.ModelAdmin):
    list_display = ('vendor_name', 'product_purchased', 'category', 'quantity_purchased', 'purchase_price', 'length', 'height', 'width', 'total_purchase_amount', 'payment_made', 'balance_remaining', 'payment_date')
    list_filter = ('vendor_name', 'payment_date', 'category')
    search_fields = ('vendor_name', 'product_purchased')
    readonly_fields = ('total_purchase_amount', 'balance_remaining', 'payment_date')
    date_hierarchy = 'payment_date'
    exclude = ('product',)

    fieldsets = (
        ('Vendor Information', {
            'fields': ('vendor_name', 'category')
        }),
        ('Product Details', {
            'fields': ('product_purchased', 'quantity_purchased', 'purchase_price')
        }),
        ('Product Dimensions', {
            'fields': ('length', 'height', 'width')
        }),
        ('Payment Information', {
            'fields': ('total_purchase_amount', 'payment_made', 'balance_remaining', 'payment_date', 'notes')
        })
    )

    # Admin UX defaults
    list_per_page = 100


    def save_model(self, request, obj, form, change):
        # Signals handle stock creation; just save the VendorPayment
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-payment_date')


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'total_payment', 'total_paid', 'payment_left')
    search_fields = ('name',)
    ordering = ('name',)
