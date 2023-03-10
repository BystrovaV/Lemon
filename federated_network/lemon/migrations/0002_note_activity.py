# Generated by Django 4.1.3 on 2022-11-20 09:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("lemon", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Note",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ap_id", models.TextField(null=True)),
                ("remote", models.BooleanField(default=False)),
                ("content", models.CharField(max_length=500)),
                (
                    "likes",
                    models.ManyToManyField(related_name="liked", to="lemon.person"),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="lemon.person",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Activity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ap_id", models.TextField()),
                ("payload", models.BinaryField()),
                ("created_at", models.DateField(auto_now_add=True)),
                ("remote", models.BooleanField(default=False)),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="lemon.person",
                    ),
                ),
            ],
        ),
    ]
