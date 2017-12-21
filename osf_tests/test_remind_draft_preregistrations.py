import pytest
from website import settings
from django.utils import timezone
from framework.auth.core import Auth

from website.prereg.utils import get_prereg_schema

from .factories import UserFactory, DraftRegistrationFactory

from osf.models import QueuedMail
from osf.models.queued_mail import PREREG_REMINDER_TYPE

from scripts.remind_draft_preregistrations import silly_test

@pytest.fixture()
def user():
    return UserFactory(is_registered=True)

@pytest.fixture()
def schema():
    return get_prereg_schema()

@pytest.mark.django_db
class TestPreregReminder:

    @pytest.fixture()
    def draft(self, user, schema):
        draft = DraftRegistrationFactory(
            registration_schema=schema, initiator=user
        )
        draft.datetime_initiated = timezone.now() - settings.PREREG_WAIT_TIME
        draft.save()
        return draft


    def test_trigger_prereg_reminder(self, draft):
        silly_test(dry_run=False)

        assert QueuedMail.objects.filter(email_type=PREREG_REMINDER_TYPE).count() == 1

    def test_dont_trigger_prereg_reminder_already_queued(self, draft):
        silly_test(dry_run=False)
        silly_test(dry_run=False)

        assert QueuedMail.objects.filter(email_type=PREREG_REMINDER_TYPE).count() == 1

    def test_dont_trigger_prereg_reminder_too_new(self, schema):
        DraftRegistrationFactory(registration_schema=schema)
        silly_test(dry_run=False)

        assert QueuedMail.objects.filter(email_type=PREREG_REMINDER_TYPE).count() == 0

    def test_dont_trigger_prereg_reminder_too_old(self, draft):
        draft.datetime_initiated = timezone.now() - settings.PREREG_AGE_LIMIT
        draft.save()
        silly_test(dry_run=False)

        assert QueuedMail.objects.filter(email_type=PREREG_REMINDER_TYPE).count() == 0

    def test_dont_trigger_prereg_reminder_draft_submitted(self, user, draft):
        draft.register(Auth(user))
        draft.save()
        silly_test(dry_run=False)

        assert QueuedMail.objects.filter(email_type=PREREG_REMINDER_TYPE).count() == 0

    def test_dont_trigger_prereg_reminder_wrong_schema(self):
        draft = DraftRegistrationFactory()
        draft.datetime_initiated = timezone.now() - settings.PREREG_WAIT_TIME
        draft.save()
        silly_test(dry_run=False)

        assert QueuedMail.objects.filter(email_type=PREREG_REMINDER_TYPE).count() == 0

    def test_dont_trigger_prereg_reminder_deleted_draft(self, draft):
        draft.deleted = timezone.now()
        draft.save()
        silly_test(dry_run=False)

        assert QueuedMail.objects.filter(email_type=PREREG_REMINDER_TYPE).count() == 0
