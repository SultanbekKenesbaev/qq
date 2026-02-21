from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Product, ProductSize, ProductImage, Review


class ClientRegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Ат', max_length=50)
    last_name = forms.CharField(label='Фамилия', max_length=50)
    phone = forms.CharField(label='Телефон номер', max_length=20)
    gender = forms.ChoiceField(label='Жыныс', choices=[('male','Еркек'),('female','Аял')])
    height = forms.FloatField(label='Бой (см)', min_value=100, max_value=250)
    weight = forms.FloatField(label='Салмақ (кг)', min_value=30, max_value=300)
    size = forms.ChoiceField(label='Размер', choices=[('XS','XS'),('S','S'),('M','M'),('L','L'),('XL','XL'),('XXL','XXL'),('XXXL','XXXL')])

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'phone', 'gender', 'height', 'weight', 'size', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'client'
        if commit:
            user.save()
        return user


class SellerRegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Ат', max_length=50)
    last_name = forms.CharField(label='Фамилия', max_length=50)
    shop_name = forms.CharField(label='Дүкан аты', max_length=100)
    phone = forms.CharField(label='Телефон номер', max_length=20)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'shop_name', 'phone', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'seller'
        if commit:
            user.save()
        return user


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'gender', 'height', 'weight', 'size', 'avatar']


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'gender', 'style', 'description']
        labels = {
            'name': 'Өним аты',
            'category': 'Категория',
            'price': 'Баҳа (сум)',
            'gender': 'Жыныс',
            'style': 'Стиль',
            'description': 'Сыпатлама',
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        labels = {'rating': 'Баҳа', 'comment': 'Пикир'}
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} ⭐') for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }
