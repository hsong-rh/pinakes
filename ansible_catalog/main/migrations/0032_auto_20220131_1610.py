# Generated by Django 3.2.9 on 2022-01-31 16:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0031_create_default_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="Role",
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
                ("name", models.CharField(max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name="group",
            name="roles",
            field=models.ManyToManyField(to="main.Role"),
        ),
    ]
