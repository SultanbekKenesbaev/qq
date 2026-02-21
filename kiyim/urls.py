from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_choice, name='register_choice'),
    path('register/client/', views.register_client, name='register_client'),
    path('register/seller/', views.register_seller, name='register_seller'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Client
    path('dashboard/', views.client_dashboard, name='client_dashboard'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),

    # Seller
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/product/add/', views.add_product, name='add_product'),
    path('seller/product/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('seller/product/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('seller/order/<int:pk>/status/', views.update_order_status, name='update_order_status'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),

    # Virtual Try-On
    path('try-on/', views.virtual_tryon, name='virtual_tryon'),
    path('try-on/<int:product_pk>/', views.virtual_tryon, name='virtual_tryon_product'),
    path('try-on/api/run/', views.tryon_api_run, name='tryon_api_run'),
    path('try-on/api/status/<str:prediction_id>/', views.tryon_api_status, name='tryon_api_status'),

    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
]
# این файлды толықтырамыз — жоқарыдағы urlpatterns-ке қосылады
