import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from .models import Product, Favorite, Order, ContactSubmission, UserInteractionLog

ADMIN_EMAILS = ['admin@hci.com', 'professor@hci.com']


def _get_or_create_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def is_admin_user(user):
    return user.is_authenticated and (user.is_superuser or user.email.lower() in [e.lower() for e in ADMIN_EMAILS])


# --- Storefront Catalog Views ---

def index(request):
    """Main Catalog Page"""
    _get_or_create_session(request)

    # Populate sample inventory if empty
    if not Product.objects.exists():
        sample_products = [
            Product(name="Wireless Noise-Canceling Headphones", brand="AudioPro", price=199.99, description="High-fidelity wireless sound with active noise cancellation.", image_url="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400", category="Electronics"),
            Product(name="Minimalist Smart Watch", brand="TechTime", price=149.50, description="Sleek fitness tracking smartwatch with 7-day battery life.", image_url="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400", category="Wearables"),
            Product(name="Ergonomic Leather Sneakers", brand="UrbanStep", price=89.99, description="Ultra-comfortable daily sneakers crafted with breathable leather.", image_url="https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400", category="Footwear"),
            Product(name="Classic Stainless Water Bottle", brand="EcoFlask", price=29.99, description="Insulated bottle keeping beverages cold for up to 24 hours.", image_url="https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=400", category="Accessories"),
        ]
        Product.objects.bulk_create(sample_products)

    products = Product.objects.all()
    user_favorites = []
    if request.user.is_authenticated:
        user_favorites = Favorite.objects.filter(user=request.user).values_list('product_id', flat=True)

    return render(request, 'index.html', {
        'products': products,
        'user_favorites': user_favorites,
        'is_admin': is_admin_user(request.user)
    })


def product_detail(request, product_id):
    """Single Product Details View"""
    _get_or_create_session(request)
    product = get_object_or_404(Product, id=product_id)
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, product=product).exists()

    return render(request, 'product_detail.html', {
        'product': product,
        'is_favorite': is_favorite,
        'is_admin': is_admin_user(request.user)
    })


# --- Shopping Cart Views ---

def _get_cart(request):
    return request.session.get('cart', {})


def _save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


def add_to_cart(request, product_id):
    """Adds item to session cart"""
    product = get_object_or_404(Product, id=product_id)
    cart = _get_cart(request)
    str_id = str(product_id)

    cart[str_id] = cart.get(str_id, 0) + 1
    _save_cart(request, cart)

    UserInteractionLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_id=request.session.session_key or 'anonymous',
        page_url=request.path,
        action_type='add_to_cart',
        product_id=product.id,
        element_id='add_to_cart_btn',
        details=f"Added {product.name} to cart"
    )
    return redirect('cart_detail')


def remove_from_cart(request, product_id):
    """Removes item from session cart"""
    cart = _get_cart(request)
    str_id = str(product_id)
    if str_id in cart:
        del cart[str_id]
        _save_cart(request, cart)
    return redirect('cart_detail')


def cart_detail(request):
    """Displays cart page"""
    cart = _get_cart(request)
    cart_items = []
    total_price = 0

    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(id=int(product_id))
            item_total = product.price * quantity
            total_price += item_total
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'item_total': item_total
            })
        except Product.DoesNotExist:
            continue

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'is_admin': is_admin_user(request.user)
    })


@login_required
def checkout(request):
    """Converts items in cart into completed Orders"""
    cart = _get_cart(request)
    if not cart:
        return redirect('index')

    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(id=int(product_id))
            Order.objects.create(
                user=request.user,
                product=product,
                quantity=quantity,
                total_price=product.price * quantity
            )
        except Product.DoesNotExist:
            continue

    request.session['cart'] = {}
    request.session.modified = True
    return redirect('profile')


# --- User Profile & Favorites ---

@login_required
def toggle_favorite(request, product_id):
    """Adds/removes product from user favorites"""
    product = get_object_or_404(Product, id=product_id)
    fav, created = Favorite.objects.get_or_create(user=request.user, product=product)
    if not created:
        fav.delete()
    return redirect(request.META.get('HTTP_REFERER', 'index'))


@login_required
def profile(request):
    """User profile displaying order history and saved items"""
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    orders = Order.objects.filter(user=request.user).select_related('product').order_by('-created_at')
    return render(request, 'profile.html', {
        'favorites': favorites,
        'orders': orders,
        'is_admin': is_admin_user(request.user)
    })


# --- Authentication Views ---

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(username=user_obj.username, password=password)
            if user:
                login(request, user)
                return redirect('index')
        except User.DoesNotExist:
            pass
        return render(request, 'login.html', {'error': 'Invalid email or password.'})
    return render(request, 'login.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            return render(request, 'register.html', {'error': 'Username or Email already taken.'})

        user = User.objects.create_user(username=username, email=email, password=password)
        if email.lower() in [e.lower() for e in ADMIN_EMAILS]:
            user.is_staff = True
            user.save()

        login(request, user)
        return redirect('index')
    return render(request, 'register.html')


def logout_view(request):
    logout(request)
    return redirect('index')


# --- Admin Inventory & Analytics Dashboard ---

@login_required
def manage_products(request):
    """Admin product entry & table management"""
    if not is_admin_user(request.user):
        return HttpResponseForbidden("Access Denied: Admin privileges required.")

    if request.method == 'POST':
        name = request.POST.get('name')
        brand = request.POST.get('brand')
        price = request.POST.get('price')
        category = request.POST.get('category')
        description = request.POST.get('description')
        image_file = request.FILES.get('image')
        image_url = request.POST.get('image_url', '')

        Product.objects.create(
            name=name,
            brand=brand,
            price=price,
            category=category,
            description=description,
            image=image_file,
            image_url=image_url if not image_file else ''
        )
        return redirect('manage_products')

    products = Product.objects.all().order_by('-created_at')
    return render(request, 'manage_products.html', {
        'products': products,
        'is_admin': True
    })


@login_required
def analytics_dashboard(request):
    """Admin Click Tracking Analytics"""
    if not is_admin_user(request.user):
        return HttpResponseForbidden("Access Denied: You must be an administrator to view this dashboard.")

    total_views = UserInteractionLog.objects.filter(action_type='page_view').count()
    total_clicks = UserInteractionLog.objects.filter(action_type='button_click').count()
    total_purchases = Order.objects.count()

    most_clicked_products = UserInteractionLog.objects.filter(product_id__isnull=False) \
        .values('product_id') \
        .annotate(click_count=Count('id')) \
        .order_by('-click_count')

    top_products = []
    for item in most_clicked_products:
        try:
            prod = Product.objects.get(id=item['product_id'])
            top_products.append({'product': prod, 'clicks': item['click_count']})
        except Product.DoesNotExist:
            pass

    top_elements = UserInteractionLog.objects.filter(action_type='button_click') \
        .values('element_id', 'element_text') \
        .annotate(count=Count('id')) \
        .order_by('-count')[:10]

    recent_logs = UserInteractionLog.objects.order_by('-timestamp')[:25]

    return render(request, 'analytics.html', {
        'total_views': total_views,
        'total_clicks': total_clicks,
        'total_purchases': total_purchases,
        'top_products': top_products,
        'top_elements': top_elements,
        'recent_logs': recent_logs,
        'is_admin': True
    })


# --- API & Contact ---

@csrf_exempt
def log_event_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            session_id = request.session.session_key or 'anonymous'
            user = request.user if request.user.is_authenticated else None

            UserInteractionLog.objects.create(
                user=user,
                session_id=session_id,
                page_url=data.get('page_url', ''),
                action_type=data.get('action_type', 'click'),
                element_id=data.get('element_id', ''),
                element_text=data.get('element_text', ''),
                product_id=data.get('product_id', None),
                details=data.get('details', '')
            )
            return JsonResponse({'status': 'success'}, status=201)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid_method'}, status=405)


def contact(request):
    _get_or_create_session(request)
    success = False
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message', '')
        ContactSubmission.objects.create(full_name=name, email=email, message=message)
        success = True
    return render(request, 'contact.html', {'success': success, 'is_admin': is_admin_user(request.user)})


from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

@login_required
def analytics_dashboard(request):
    """Enhanced Admin Analytics & Database Dashboard"""
    if not is_admin_user(request.user):
        return HttpResponseForbidden("Access Denied: You must be an administrator to view this dashboard.")

    # High-level KPIs
    total_views = UserInteractionLog.objects.filter(action_type='page_view').count()
    total_clicks = UserInteractionLog.objects.filter(action_type='button_click').count()
    total_purchases = Order.objects.count()
    total_revenue = Order.objects.aggregate(Sum('total_price'))['total_price__sum'] or 0
    total_users = User.objects.count()
    total_products = Product.objects.count()

    # Trend Data: Daily Purchases & Revenue
    daily_sales = Order.objects.annotate(date=TruncDate('created_at')) \
        .values('date') \
        .annotate(daily_total=Sum('total_price'), order_count=Count('id')) \
        .order_by('-date')[:10]

    # Trend Data: Daily Interactive Clicks
    daily_clicks = UserInteractionLog.objects.annotate(date=TruncDate('timestamp')) \
        .values('date') \
        .annotate(click_count=Count('id')) \
        .order_by('-date')[:10]

    # Product Performance
    most_clicked_products = UserInteractionLog.objects.filter(product_id__isnull=False) \
        .values('product_id') \
        .annotate(click_count=Count('id')) \
        .order_by('-click_count')

    top_products = []
    for item in most_clicked_products:
        try:
            prod = Product.objects.get(id=item['product_id'])
            top_products.append({'product': prod, 'clicks': item['click_count']})
        except Product.DoesNotExist:
            pass

    # UI Element Click Heatmap
    top_elements = UserInteractionLog.objects.filter(action_type='button_click') \
        .values('element_id', 'element_text') \
        .annotate(count=Count('id')) \
        .order_by('-count')[:10]

    # Complete DB Tables Data
    users = User.objects.all().order_by('-date_joined')
    all_orders = Order.objects.select_related('user', 'product').order_by('-created_at')
    contact_messages = ContactSubmission.objects.order_by('-created_at')
    all_logs = UserInteractionLog.objects.select_related('user').order_by('-timestamp')[:100]
    all_products = Product.objects.all().order_by('-created_at')

    context = {
        'total_views': total_views,
        'total_clicks': total_clicks,
        'total_purchases': total_purchases,
        'total_revenue': total_revenue,
        'total_users': total_users,
        'total_products': total_products,
        'daily_sales': list(daily_sales),
        'daily_clicks': list(daily_clicks),
        'top_products': top_products,
        'top_elements': top_elements,
        'users': users,
        'all_orders': all_orders,
        'contact_messages': contact_messages,
        'all_logs': all_logs,
        'all_products': all_products,
        'is_admin': True,
    }
    return render(request, 'analytics.html', context)