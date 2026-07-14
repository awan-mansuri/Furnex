from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from decimal import Decimal
from django.db.models import Sum
from .models import VendorPayment, Product, StockManagement, Category, Vendor

@receiver(post_save, sender=VendorPayment)
def create_stock_from_vendor_payment(sender, instance, created, **kwargs):
    """
    When a VendorPayment is created, add a StockManagement entry only.
    Do not create or update Product automatically.
    """
    if not created:
        return
    category = instance.category
    StockManagement.objects.create(
        product=None,
        product_category=category if category else None,
        product_name=instance.product_purchased,
        product_price=instance.purchase_price,
        product_quantity=instance.quantity_purchased,
        total_price=instance.total_purchase_amount,
        current_stock=instance.quantity_purchased,
        supplier_name=instance.vendor_name,
        length=instance.length,
        height=instance.height,
        width=instance.width,
    )


def _recalculate_vendor_summary(vendor_name: str):
    if not vendor_name:
        return
    aggregates = VendorPayment.objects.filter(vendor_name=vendor_name).aggregate(
        total_payment=Sum('total_purchase_amount') or Decimal('0'),
        total_paid=Sum('payment_made') or Decimal('0'),
        payment_left=Sum('balance_remaining') or Decimal('0'),
    )
    total_payment = aggregates.get('total_payment') or Decimal('0')
    total_paid = aggregates.get('total_paid') or Decimal('0')
    payment_left = aggregates.get('payment_left') or Decimal('0')
    vendor_obj, _ = Vendor.objects.get_or_create(name=vendor_name)
    vendor_obj.total_payment = total_payment
    vendor_obj.total_paid = total_paid
    vendor_obj.payment_left = payment_left
    vendor_obj.save()


@receiver(pre_save, sender=VendorPayment)
def _cache_old_vendor_name(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_vendor_name = None
        return
    try:
        old = VendorPayment.objects.get(pk=instance.pk)
        instance._old_vendor_name = old.vendor_name
    except VendorPayment.DoesNotExist:
        instance._old_vendor_name = None


@receiver(post_save, sender=VendorPayment)
def update_vendor_summary_on_save(sender, instance, created, **kwargs):
    # Recalculate for current vendor
    _recalculate_vendor_summary(instance.vendor_name)
    # If vendor name changed, also recalc old vendor
    old_name = getattr(instance, '_old_vendor_name', None)
    if old_name and old_name != instance.vendor_name:
        _recalculate_vendor_summary(old_name)


@receiver(post_delete, sender=VendorPayment)
def update_vendor_summary_on_delete(sender, instance, **kwargs):
    _recalculate_vendor_summary(instance.vendor_name)

@receiver(post_save, sender=Product)
def noop_on_product_create(sender, instance, created, **kwargs):
    """No automatic stock creation on product create."""
    return