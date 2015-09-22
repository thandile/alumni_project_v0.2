# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('alumni', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='end_date',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='start_date',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
