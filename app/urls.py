from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path(settings.URL_PREFIX + '/jet/', include('jet.urls', 'jet')),
    path(settings.URL_PREFIX + '/admin/', admin.site.urls),
    path(settings.URL_PREFIX + '/lunchinator/', include('lunchinator.urls')),
    path(f'{settings.STATIC_URL.strip("/")}/<path:path>', serve, {'document_root': settings.STATIC_ROOT})
]
