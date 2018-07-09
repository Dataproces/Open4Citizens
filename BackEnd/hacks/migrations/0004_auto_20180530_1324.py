# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2018-05-30 11:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hacks', '0003_event_manual_validation'),
    ]

    operations = [
        migrations.AddField(
            model_name='pilot',
            name='imgname',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='manual_validation',
            field=models.BooleanField(default=True),
        ),
    ]
