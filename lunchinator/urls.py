from django.urls import path
from lunchinator.views import endpoint, trigger

urlpatterns = [
    path('endpoint', endpoint),
    path('trigger', trigger)
]
