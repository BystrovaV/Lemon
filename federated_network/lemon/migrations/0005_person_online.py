# Generated by Django 4.1.3 on 2023-07-08 18:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lemon", "0004_person_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="person", name="online", field=models.IntegerField(default=0),
        ),
    ]