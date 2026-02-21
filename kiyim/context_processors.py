def cart_count(request):
    count = 0
    if request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role == 'client':
        count = request.user.cart_items.count()
    return {'cart_count': count}
