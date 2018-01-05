#!/usr/bin/env python
# encoding: utf-8
"""Verify that all `OsfStorageFileVersion` records created earlier than two
days before the latest inventory report are contained in the inventory, point
to the correct Glacier archive, and have an archive of the correct size.
Should be run after `glacier_inventory.py`.
"""

import gc
import json
import logging

from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

from framework.celery_tasks import app as celery_app

from website.app import init_app
from osf.models import FileVersion

from scripts import utils as scripts_utils
from scripts.osfstorage import settings as storage_settings
from scripts.osfstorage import utils as storage_utils


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Glacier inventories take about four hours to generate and reflect files added
# about a day before the request is made; only check records created over two
# days before the job.
DELTA_DATE = relativedelta(days=2)


class AuditError(Exception):
    pass


class NotFound(AuditError):
    pass


class BadSize(AuditError):
    pass


class BadArchiveId(AuditError):
    pass


def get_targets(date):
    return FileVersion.objects.filter(
        created__lt=date - DELTA_DATE, metadata__has_key='archive', location__isnull=False
    ).iterator()


def check_glacier_version(version, inventory):
    data = inventory.get(version.metadata['archive'])
    if data is None:
        raise NotFound('Glacier archive for version {} not found'.format(version._id))
    if version.metadata['archive'] != data['ArchiveId']:
        raise BadArchiveId(
            'Glacier archive for version {} has incorrect archive ID {} (expected {})'.format(
                version._id,
                data['ArchiveId'],
                version.metadata['archive'],
            )
        )
    if (version.size or version.metadata.get('size')) != data['Size']:
        raise BadSize(
            'Glacier archive for version {} has incorrect size {} (expected {})'.format(
                version._id,
                data['Size'],
                version.size,
            )
        )


def main(job_id=None):
    glacier = storage_utils.get_glacier_resource()

    if job_id:
        job = glacier.Job(
            storage_settings.GLACIER_VAULT_ACCOUNT_ID,
            storage_settings.GLACIER_VAULT_NAME,
            job_id,
        )
    else:
        vault = storage_utils.get_glacier_resource().Vault(
            storage_settings.GLACIER_VAULT_ACCOUNT_ID,
            storage_settings.GLACIER_VAULT_NAME
        )
        jobs = vault.completed_jobs.all()
        if not jobs:
            raise RuntimeError('No completed jobs found')
        job = sorted(jobs, key=lambda job: job.creation_date)[-1]

    response = job.get_output()
    output = json.loads(response['body'].read().decode('utf-8'))
    creation_date = parse_date(job.creation_date)
    inventory = {
        each['ArchiveId']: each
        for each in output['ArchiveList']
    }

    for idx, version in enumerate(get_targets(creation_date)):
        try:
            check_glacier_version(version, inventory)
        except AuditError as error:
            logger.error(str(error))
        if idx % 1000 == 0:
            gc.collect()


@celery_app.task(name='scripts.osfstorage.glacier_audit')
def run_main(job_id=None, dry_run=True):
    init_app(set_backends=True, routes=False)
    if not dry_run:
        scripts_utils.add_file_logger(logger, __file__)
    main(job_id=job_id)
