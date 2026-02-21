from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('kiyim.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if getattr(settings, 'SERVE_MEDIA_WITH_DJANGO', False) and not settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', static_serve, {'document_root': settings.MEDIA_ROOT}),
    ]

if getattr(settings, 'SERVE_STATIC_WITH_DJANGO', False) and not settings.DEBUG:
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', static_serve, {'document_root': settings.STATIC_ROOT}),
    ]
