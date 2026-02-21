#!/bin/bash
# MODA Kiyim Platform — Ishga tushirish skripti
# Qoraqolpoq tilida kiyim marketplace

echo "========================================"
echo "  MODA — Kiyim Platform"
echo "  Qoraqolpoq tilida"
echo "========================================"

# Install dependencies
echo "[1/4] Django va Pillow o'rnatilmoqda..."
pip install Django Pillow

# Create migrations
echo "[2/4] Database migratsiyasi..."
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional)
echo "[3/4] Admin foydalanuvchi yaratish (ixtiyoriy)..."
echo "from kiyim.models import User; User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin','admin@moda.uz','admin123', role='client', shop_name='Admin')" | python manage.py shell

# Collect static files
echo "[4/4] Static fayllar..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo ""
echo "========================================"
echo "  Ishga tushirilmoqda: http://localhost:8000"
echo "  Admin: http://localhost:8000/admin/"
echo "  Login: admin / admin123"
echo "========================================"

python manage.py runserver
