# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-12-08 18:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import osf.utils.datetime_aware_jsonfield
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0022_auto_20161118_1600'),
    ]

    operations = [
        migrations.AddField(
            model_name='preprintprovider',
            name='access_token',
            field=osf.utils.fields.EncryptedTextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='advisory_board',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='email_contact',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='email_support',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='example',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='licenses_acceptable',
            field=models.ManyToManyField(blank=True, to='osf.NodeLicense'),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='social_facebook',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='social_twitter',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='preprintprovider',
            name='subjects_acceptable',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(default=list),
        ),
        migrations.AlterField(
            model_name='draftregistrationapproval',
            name='initiation_date',
            field=osf.utils.fields.NonNaiveDatetimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.AlterField(
            model_name='embargo',
            name='initiation_date',
            field=osf.utils.fields.NonNaiveDatetimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.AlterField(
            model_name='embargoterminationapproval',
            name='initiation_date',
            field=osf.utils.fields.NonNaiveDatetimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.AlterField(
            model_name='registrationapproval',
            name='initiation_date',
            field=osf.utils.fields.NonNaiveDatetimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.AlterField(
            model_name='retraction',
            name='initiation_date',
            field=osf.utils.fields.NonNaiveDatetimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
    ]
