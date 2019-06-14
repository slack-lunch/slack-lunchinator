from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models


class Restaurant(models.Model):
    acronym = models.CharField(max_length=5)
    enabled = models.BooleanField(default=True)
    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=255)
    url = models.URLField()

    class Meta:
        ordering = 'acronym',
        default_related_name = 'restaurants'

    def __str__(self):
        return f'Restaurant: {self.acronym}: {self.name} ({self.url})'


class User(AbstractBaseUser):
    slack_id = models.CharField(max_length=20)
    favorite_restaurants = models.ManyToManyField(Restaurant)

    class Meta:
        verbose_name_plural = 'Users (with favorite restaurants)'

    def __str__(self):
        return f'User: {self}'


class Meal(models.Model):
    date = models.DateField(auto_now=True)
    name = models.CharField(max_length=255)
    price = models.FloatField()
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)

    class Meta:
        ordering = '-date', 'restaurant', 'id'
        default_related_name = 'meals'


class Selection(models.Model):
    recommended = models.BooleanField(default=False)
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        default_related_name = 'selections'
