# Generated by Django 2.2.2 on 2019-06-20 09:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lunchinator', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='restaurant',
            options={'default_related_name': 'restaurants', 'ordering': ('name',)},
        ),
        migrations.RemoveField(
            model_name='restaurant',
            name='acronym',
        ),
    ]
