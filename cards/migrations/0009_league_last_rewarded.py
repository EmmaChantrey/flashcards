# Generated by Django 4.2.16 on 2025-02-15 17:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cards', '0008_remove_leagueuser_last_reset'),
    ]

    operations = [
        migrations.AddField(
            model_name='league',
            name='last_rewarded',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
