from django.urls import path, include
from . import views
from .views import create_back_in_stock_alert

urlpatterns = [
    # Remove this line
    # path('accounts/', include('django.contrib.auth.urls')),
    
    # Add these new paths
    path('login/', views.login_view, name='login'),
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Admin dashboard URL
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Password reset URLs
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/done/', views.password_reset_done_view, name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete_view, name='password_reset_complete'),
      
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('shop/', views.shop, name='shop'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('product/<int:product_id>/review/', views.review_submit, name='review_submit'),
    path('services/', views.services, name='services'),
    path('contact/', views.contact, name='contact'),
    path('blog/', views.blog, name='blog'),
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
    path('update-cart/', views.update_cart, name='update_cart'),
    path('remove-from-cart/<int:cart_item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    path('process-order/', views.process_order, name='process_order'),
    path('thankyou/', views.thankyou_view, name='thankyou'),
    
    # Razorpay payment URLs
    path('create-razorpay-order/', views.create_razorpay_order, name='create_razorpay_order'),
    path('razorpay-payment-success/', views.razorpay_payment_success, name='razorpay_payment_success'),
    path('razorpay-payment-failure/', views.razorpay_payment_failure, name='razorpay_payment_failure'),
    path('payment-success/', views.payment_success_view, name='payment_success'),
    path('payment-failure/', views.payment_failure_view, name='payment_failure'),
    # Admin dashboard data for admin index chart
    path('admin-dashboard-data/', views.admin_dashboard_data, name='admin_dashboard_data'),
    # Invoices
    path('invoice/<int:order_id>/', views.invoice_view, name='invoice'),
    # Note: cannot use /admin/... because it's captured by Django admin
    path('order-invoice/<int:order_id>/', views.admin_invoice_view, name='admin_invoice'),
    # Admin data endpoints
    path('admin-model-counts/', views.admin_model_counts, name='admin_model_counts'),
    path('retry-email-queue/', views.retry_email_queue_view, name='retry_email_queue'),
    # PDF invoice
    path('invoice/<int:order_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    
    # Address management URLs
    path('profile/', views.user_profile_view, name='user_profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('profile/remove-avatar/', views.remove_avatar, name='remove_avatar'),
    path('profile/add-address/', views.add_address_view, name='add_address'),
    path('profile/edit-address/<int:address_id>/', views.edit_address_view, name='edit_address'),
    path('profile/delete-address/<int:address_id>/', views.delete_address_view, name='delete_address'),
    path('profile/set-default-address/<int:address_id>/', views.set_default_address_view, name='set_default_address'),
    
    # Notification URLs
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # Wishlist URLs
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('wishlist/clear/', views.clear_wishlist, name='clear_wishlist'),
    
    # Compare URLs
    path('compare/', views.compare_view, name='compare'),
    path('compare/toggle/<int:product_id>/', views.toggle_compare, name='toggle_compare'),
    path('compare/clear/', views.clear_compare, name='clear_compare'),
    
    # User Coupon URLs (using unified coupon system)
    # Note: apply_coupon and remove_coupon now handle all coupon types consistently
    path('apply-user-coupon/', views.apply_coupon, name='apply_user_coupon'),  # Alias for backward compatibility
    path('remove-user-coupon/', views.remove_coupon, name='remove_user_coupon'),  # Alias for backward compatibility
    
    # Order Tracking URLs
    path('track-order/', views.track_order, name='track_order'),
    path('track-order-ajax/', views.track_order_ajax, name='track_order_ajax'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('my-orders/', views.my_orders, name='my_orders'),
    
    # Return functionality URLs
    path('return-order/<int:order_id>/', views.return_order, name='return_order'),
    path('submit-return/', views.submit_return, name='submit_return'),
    
    # Product Alerts (NEW FEATURE)
    path('api/create-alert/', views.create_product_alert, name='create_alert'),
    
    # Gift Registry (NEW FEATURE)
    path('create-registry/', views.create_registry, name='create_registry'),
    path('registry/<str:code>/', views.view_registry, name='view_registry'),
    path('my-registries/', views.my_registries, name='my_registries'),
    
    # Assembly Service (NEW FEATURE)
    path('api/assembly-services/', views.get_assembly_services, name='get_assembly_services'),
    path('api/book-assembly/', views.book_assembly_service, name='book_assembly'),
    
    # Recommendations (NEW FEATURE)
    path('api/recommendations/<int:product_id>/', views.get_recommendations, name='get_recommendations'),
    path('api/track-view/<int:product_id>/', views.track_product_view, name='track_product_view'),
    
    # Live Chat (NEW FEATURE)
    path('chat/', views.chat_view, name='chat'),
    path('api/send-message/', views.send_chat_message, name='send_chat_message'),
    
    # Chatbot API (FAQ-based responses)
    path('api/chatbot-response/', views.chatbot_response, name='chatbot_response'),
]

urlpatterns += [
    path('back-in-stock-alert/', create_back_in_stock_alert, name='create_back_in_stock_alert'),
]
