# Generated by Django 2.2.2 on 2019-06-20 09:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lunchinator', '0002_auto_20190620_0914'),
    ]

    operations = [
        migrations.AlterField(
            model_name='meal',
            name='price',
            field=models.FloatField(null=True),
        ),
    ]