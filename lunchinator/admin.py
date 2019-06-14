from django.contrib import admin
from lunchinator.models import User, Restaurant, Meal, Selection

admin.site.register(User)
admin.site.register(Restaurant)
admin.site.register(Meal)
admin.site.register(Selection)
