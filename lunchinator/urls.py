from django.urls import path
from lunchinator.views import endpoint, slash, trigger, dashboard

urlpatterns = [
    path('endpoint', endpoint),
    path('slash', slash),
    path('trigger', trigger),
    path('dashboard', dashboard)
]
