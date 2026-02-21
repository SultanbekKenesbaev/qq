from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from .models import User, Product, ProductImage, ProductSize, Cart, Order, OrderItem, Review, CATEGORY_CHOICES
from .forms import ClientRegisterForm, SellerRegisterForm, ClientProfileForm, ProductForm, ReviewForm


def home(request):
    featured = Product.objects.filter(is_active=True).order_by('-views_count')[:8]
    new_arrivals = Product.objects.filter(is_active=True).order_by('-created_at')[:8]
    categories = CATEGORY_CHOICES
    return render(request, 'kiyim/home.html', {
        'featured': featured,
        'new_arrivals': new_arrivals,
        'categories': categories,
    })


def register_choice(request):
    return render(request, 'kiyim/register_choice.html')


def register_client(request):
    if request.method == 'POST':
        form = ClientRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Сәтли дизимге алындыңыз!')
            return redirect('client_dashboard')
    else:
        form = ClientRegisterForm()
    return render(request, 'kiyim/register_client.html', {'form': form})


def register_seller(request):
    if request.method == 'POST':
        form = SellerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Дүканыңыз дизимге алынды!')
            return redirect('seller_dashboard')
    else:
        form = SellerRegisterForm()
    return render(request, 'kiyim/register_seller.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.role == 'seller':
                return redirect('seller_dashboard')
            return redirect('client_dashboard')
        messages.error(request, 'Логин яки пароль қәте!')
    return render(request, 'kiyim/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def client_dashboard(request):
    if request.user.role != 'client':
        return redirect('seller_dashboard')
    
    # AI Recommendation based on size, gender, BMI
    user = request.user
    recommendations = Product.objects.filter(is_active=True)
    
    if user.gender:
        g_map = {'male': ['male', 'unisex'], 'female': ['female', 'unisex']}
        recommendations = recommendations.filter(gender__in=g_map.get(user.gender, ['unisex']))
    
    if user.size:
        recommendations = recommendations.filter(sizes__size=user.size, sizes__quantity__gt=0).distinct()
    
    bmi = user.bmi()
    bmi_category = ''
    if bmi:
        if bmi < 18.5:
            bmi_category = 'Арық'
        elif bmi < 25:
            bmi_category = 'Қалыпты'
        elif bmi < 30:
            bmi_category = 'Артықша салмақ'
        else:
            bmi_category = 'Семириўшиликте'

    orders = user.orders.all().order_by('-created_at')[:5]
    
    return render(request, 'kiyim/client_dashboard.html', {
        'recommendations': recommendations[:12],
        'bmi': bmi,
        'bmi_category': bmi_category,
        'orders': orders,
        'categories': CATEGORY_CHOICES,
    })


@login_required
def seller_dashboard(request):
    if request.user.role != 'seller':
        return redirect('client_dashboard')
    
    products = request.user.products.filter(is_active=True).annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__rating')
    )
    
    orders = OrderItem.objects.filter(product__seller=request.user).select_related('order', 'product').order_by('-order__created_at')[:20]
    
    total_revenue = OrderItem.objects.filter(product__seller=request.user).aggregate(
        total=Sum('price')
    )['total'] or 0
    
    return render(request, 'kiyim/seller_dashboard.html', {
        'products': products,
        'orders': orders,
        'total_revenue': total_revenue,
        'product_count': products.count(),
    })


@login_required
def add_product(request):
    if request.user.role != 'seller':
        return redirect('home')
    
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            
            # Save sizes
            sizes = request.POST.getlist('sizes')
            quantities = request.POST.getlist('quantities')
            for size, qty in zip(sizes, quantities):
                if size and qty:
                    ProductSize.objects.create(product=product, size=size, quantity=int(qty))
            
            # Save images
            images = request.FILES.getlist('images')
            for i, img in enumerate(images[:5]):
                ProductImage.objects.create(product=product, image=img, order=i)
            
            messages.success(request, 'Өним қосылды!')
            return redirect('seller_dashboard')
    else:
        form = ProductForm()
    
    size_choices = [('XS','XS'),('S','S'),('M','M'),('L','L'),('XL','XL'),('XXL','XXL'),('XXXL','XXXL')]
    return render(request, 'kiyim/add_product.html', {'form': form, 'size_choices': size_choices})


@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            # Update sizes
            product.sizes.all().delete()
            sizes = request.POST.getlist('sizes')
            quantities = request.POST.getlist('quantities')
            for size, qty in zip(sizes, quantities):
                if size and qty:
                    ProductSize.objects.create(product=product, size=size, quantity=int(qty))
            
            # Add new images
            new_images = request.FILES.getlist('images')
            current_count = product.images.count()
            for i, img in enumerate(new_images[:5-current_count]):
                ProductImage.objects.create(product=product, image=img, order=current_count+i)
            
            messages.success(request, 'Өним жаңаланды!')
            return redirect('seller_dashboard')
    else:
        form = ProductForm(instance=product)
    
    size_choices = [('XS','XS'),('S','S'),('M','M'),('L','L'),('XL','XL'),('XXL','XXL'),('XXXL','XXXL')]
    return render(request, 'kiyim/edit_product.html', {'form': form, 'product': product, 'size_choices': size_choices})


@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    product.is_active = False
    product.save()
    messages.success(request, 'Өним өширилди!')
    return redirect('seller_dashboard')


def product_list(request):
    products = Product.objects.filter(is_active=True).annotate(avg_rating=Avg('reviews__rating'))
    
    category = request.GET.get('category')
    gender = request.GET.get('gender')
    size = request.GET.get('size')
    style = request.GET.get('style')
    search = request.GET.get('q')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort = request.GET.get('sort', '-created_at')
    
    if category:
        products = products.filter(category=category)
    if gender:
        products = products.filter(gender__in=[gender, 'unisex'])
    if size:
        products = products.filter(sizes__size=size, sizes__quantity__gt=0).distinct()
    if style:
        products = products.filter(style=style)
    if search:
        products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    
    products = products.order_by(sort)
    
    return render(request, 'kiyim/product_list.html', {
        'products': products,
        'categories': CATEGORY_CHOICES,
        'current_category': category,
        'current_gender': gender,
        'current_size': size,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    product.views_count += 1
    product.save(update_fields=['views_count'])
    
    reviews = product.reviews.select_related('user').order_by('-created_at')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    
    review_form = ReviewForm()
    if request.method == 'POST' and request.user.is_authenticated:
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            rev = review_form.save(commit=False)
            rev.product = product
            rev.user = request.user
            rev.save()
            messages.success(request, 'Пикириңиз қосылды!')
            return redirect('product_detail', pk=pk)
    
    related = Product.objects.filter(category=product.category, is_active=True).exclude(pk=pk)[:4]
    
    return render(request, 'kiyim/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'review_form': review_form,
        'related': related,
    })


@login_required
@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    size = request.POST.get('size')
    
    if not size:
        messages.error(request, 'Размер таңлаңыз!')
        return redirect('product_detail', pk=pk)
    
    cart_item, created = Cart.objects.get_or_create(
        user=request.user, product=product, size=size,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, 'Себетке қосылды!')
    return redirect('cart')


@login_required
def cart_view(request):
    items = request.user.cart_items.select_related('product').all()
    total = sum(item.total() for item in items)
    return render(request, 'kiyim/cart.html', {'items': items, 'total': total})


@login_required
@require_POST
def remove_from_cart(request, pk):
    Cart.objects.filter(pk=pk, user=request.user).delete()
    return redirect('cart')


@login_required
@require_POST
def checkout(request):
    items = request.user.cart_items.select_related('product').all()
    if not items:
        messages.error(request, 'Себет бос!')
        return redirect('cart')
    
    address = request.POST.get('address', '')
    total = sum(item.total() for item in items)
    
    order = Order.objects.create(user=request.user, total_price=total, address=address)
    for item in items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            size=item.size,
            quantity=item.quantity,
            price=item.product.price
        )
        # Reduce stock
        ps = ProductSize.objects.filter(product=item.product, size=item.size).first()
        if ps and ps.quantity >= item.quantity:
            ps.quantity -= item.quantity
            ps.save()
    
    items.delete()
    messages.success(request, f'Буйрытма #{order.pk} берилди!')
    return redirect('order_detail', pk=order.pk)


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'kiyim/order_detail.html', {'order': order})


@login_required
def orders_list(request):
    orders = request.user.orders.all().order_by('-created_at')
    return render(request, 'kiyim/orders_list.html', {'orders': orders})


@login_required
def update_order_status(request, pk):
    if request.user.role != 'seller':
        return redirect('home')
    item = get_object_or_404(OrderItem, pk=pk, product__seller=request.user)
    new_status = request.POST.get('status')
    item.order.status = new_status
    item.order.save()
    messages.success(request, 'Статус жаңаланды!')
    return redirect('seller_dashboard')


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ClientProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль жаңаланды!')
            return redirect('client_dashboard')
    else:
        form = ClientProfileForm(instance=request.user)
    return render(request, 'kiyim/profile_edit.html', {'form': form})



# ═══════════════════════════════════════════════
# VIRTUAL TRY-ON — replicate Python пакети арқалы
# ═══════════════════════════════════════════════

def _get_category(cat):
    return {
        'ustki': 'upper_body', 'ichki': 'upper_body',
        'jemper': 'upper_body', 'pidjak': 'upper_body',
        'sport': 'upper_body', 'oyoq': 'lower_body',
        'aksesuar': 'upper_body',
    }.get(cat, 'upper_body')


@login_required
def virtual_tryon(request, product_pk=None):
    product = None
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    products = [p for p in products if p.images.exists()][:24]
    if product_pk:
        product = get_object_or_404(Product, pk=product_pk, is_active=True)
    return render(request, 'kiyim/virtual_tryon.html', {
        'product': product,
        'products': products,
    })


@login_required
def tryon_api_run(request):
    """replicate Python пакети арқалы IDM-VTON ислетиў"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST керек'}, status=405)

    api_key    = request.POST.get('api_key', '').strip()
    product_pk = request.POST.get('product_id', '').strip()
    person_file = request.FILES.get('person_image')

    if not api_key:
        return JsonResponse({'error': 'Replicate API Key кириңиз!'}, status=400)
    if not person_file:
        return JsonResponse({'error': 'Суретиңизди жүклеңиз!'}, status=400)
    if not product_pk:
        return JsonResponse({'error': 'Кийим таңлаңыз!'}, status=400)

    product = get_object_or_404(Product, pk=product_pk)
    product_img = product.images.first()
    if not product_img:
        return JsonResponse({'error': 'Өнимде сурет жоқ!'}, status=400)

    try:
        import replicate as _replicate
        import os as _os

        # API key орнатыў
        _os.environ['REPLICATE_API_TOKEN'] = api_key

        client = _replicate.Client(api_token=api_key)

        # Адам суреті — Django UploadedFile -> bytes
        person_file.seek(0)
        person_bytes = person_file.read()

        # Кийим суреті — disk файлынан оқыў
        garment_path = product_img.image.path
        with open(garment_path, 'rb') as gf:
            garment_bytes = gf.read()

        import io as _io

        # IDM-VTON модели — файлларды тікелей BytesIO арқалы жибериў
        prediction = client.predictions.create(
            version="c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4",
            input={
                "human_img":      _io.BytesIO(person_bytes),
                "garm_img":       _io.BytesIO(garment_bytes),
                "garment_des":    product.name,
                "is_checked":     True,
                "is_checked_crop": False,
                "denoise_steps":  30,
                "seed":           42,
                "category":       _get_category(product.category),
            }
        )

        return JsonResponse({
            'prediction_id': prediction.id,
            'status': prediction.status,
        })

    except Exception as e:
        err = str(e)
        if '401' in err or 'Unauthenticated' in err or 'Invalid token' in err:
            return JsonResponse({'error': 'API Key қате! replicate.com → Account → API Tokens'}, status=400)
        return JsonResponse({'error': f'Қате: {err[:300]}'}, status=500)


@login_required
def tryon_api_status(request, prediction_id):
    """Prediction статусын текшериў"""
    api_key = request.GET.get('api_key', '').strip()
    if not api_key:
        return JsonResponse({'error': 'API Key жоқ'}, status=400)

    try:
        import replicate as _replicate
        import os as _os
        _os.environ['REPLICATE_API_TOKEN'] = api_key

        client = _replicate.Client(api_token=api_key)
        prediction = client.predictions.get(prediction_id)

        output = prediction.output
        # output — list яки string болыўы мүмкин
        if isinstance(output, list) and output:
            output_url = output[0]
            # FileOutput объект болса url алыў
            if hasattr(output_url, 'url'):
                output_url = output_url.url
            else:
                output_url = str(output_url)
        elif output and not isinstance(output, list):
            output_url = str(output) if not hasattr(output, 'url') else output.url
        else:
            output_url = None

        return JsonResponse({
            'status':  prediction.status,
            'output':  output_url,
            'error':   prediction.error,
            'logs':    (prediction.logs or '')[-400:],
        })

    except Exception as e:
        return JsonResponse({'error': str(e)[:300]}, status=500)
