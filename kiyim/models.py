from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [('client', 'Klient'), ('seller', 'Sotuvchi')]
    GENDER_CHOICES = [('male', 'Erkak'), ('female', 'Ayol')]
    SIZE_CHOICES = [('XS','XS'),('S','S'),('M','M'),('L','L'),('XL','XL'),('XXL','XXL'),('XXXL','XXXL')]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client')
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    height = models.FloatField(null=True, blank=True, help_text='sm')
    weight = models.FloatField(null=True, blank=True, help_text='kg')
    size = models.CharField(max_length=5, choices=SIZE_CHOICES, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Seller fields
    shop_name = models.CharField(max_length=100, blank=True)

    def bmi(self):
        if self.height and self.weight and self.height > 0:
            h = self.height / 100
            return round(self.weight / (h * h), 1)
        return None

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


CATEGORY_CHOICES = [
    ('ustki', 'Үстки кийим'),
    ('ichki', 'Ишки кийим'),
    ('jemper', 'Жемперлер'),
    ('pidjak', 'Пиджаклар'),
    ('sport', 'Спорт кийим'),
    ('oyoq', 'Аяқ кийим'),
    ('aksesuar', 'Аксессуарлар'),
]

STYLE_CHOICES = [
    ('klassik', 'Классик'),
    ('sport', 'Спорт'),
    ('casual', 'Casual'),
    ('business', 'Бизнес'),
    ('street', 'Уличный'),
]

GENDER_PRODUCT = [('male','Еркек'),('female','Аял'),('unisex','Унисекс')]
SIZE_CHOICES = [('XS','XS'),('S','S'),('M','M'),('L','L'),('XL','XL'),('XXL','XXL'),('XXXL','XXXL')]


class Product(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    gender = models.CharField(max_length=10, choices=GENDER_PRODUCT, default='unisex')
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default='casual')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    views_count = models.IntegerField(default=0)

    def main_image(self):
        img = self.images.first()
        return img.image if img else None

    def available_sizes(self):
        return self.sizes.filter(quantity__gt=0)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']


class ProductSize(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sizes')
    size = models.CharField(max_length=5, choices=SIZE_CHOICES)
    quantity = models.IntegerField(default=0)

    class Meta:
        unique_together = ['product', 'size']


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.CharField(max_length=5)
    quantity = models.IntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def total(self):
        return self.product.price * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Күтилмекте'),
        ('accepted', 'Қабыл алынды'),
        ('shipped', 'Жолда'),
        ('delivered', 'Жеткерилди'),
        ('cancelled', 'Бас тартылды'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    address = models.TextField(blank=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.CharField(max_length=5)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    def subtotal(self):
        return self.price * self.quantity


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
