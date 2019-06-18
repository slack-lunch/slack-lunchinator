from django.urls import path
from lunchinator.views import endpoint

urlpatterns = [
    path('endpoint', endpoint),
]
