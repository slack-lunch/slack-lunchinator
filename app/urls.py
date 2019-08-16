from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('jet/', include('jet.urls', 'jet')),
    path('admin/', admin.site.urls),
    path('lunchinator/', include('lunchinator.urls')),
    path(f'{settings.STATIC_URL.strip("/")}/<path:path>', serve, {'document_root': settings.STATIC_ROOT})
]
