# Generated by Django 4.1.3 on 2022-11-18 11:54

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ap_id', models.TextField(null=True)),
                ('remote', models.BooleanField(default=False)),
                ('username', models.CharField(max_length=100)),
                ('name', models.CharField(max_length=100)),
                ('following', models.ManyToManyField(related_name='followers', to='lemon.person')),
            ],
        ),
    ]
