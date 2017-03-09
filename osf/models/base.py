
import logging
import random
from datetime import datetime

import bson
import modularodm.exceptions
import pytz
from django.contrib.contenttypes.fields import (GenericForeignKey,
                                                GenericRelation)
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import MultipleObjectsReturned
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import F
from django.db.models import ForeignKey
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from osf.utils.caching import cached_property

from osf.exceptions import ValidationError
from osf.modm_compat import to_django_query
from osf.utils.datetime_aware_jsonfield import (DateTimeAwareJSONField,
                                                coerce_nonnaive_datetimes)
from osf.utils.fields import LowercaseCharField, NonNaiveDateTimeField

ALPHABET = '23456789abcdefghjkmnpqrstuvwxyz'

logger = logging.getLogger(__name__)


def generate_guid(length=5):
    while True:
        guid_id = ''.join(random.sample(ALPHABET, length))

        try:
            # is the guid in the blacklist
            BlackListGuid.objects.get(guid=guid_id)
        except BlackListGuid.DoesNotExist:
            # it's not, check and see if it's already in the database
            try:
                Guid.objects.get(_id=guid_id)
            except Guid.DoesNotExist:
                # valid and unique guid
                return guid_id


def generate_object_id():
    return str(bson.ObjectId())


class MODMCompatibilityQuerySet(models.QuerySet):

    def __getitem__(self, k):
        item = super(MODMCompatibilityQuerySet, self).__getitem__(k)
        if hasattr(item, 'wrapped'):
            return item.wrapped()
        else:
            return item

    def __iter__(self):
        items = super(MODMCompatibilityQuerySet, self).__iter__()
        for item in items:
            if hasattr(item, 'wrapped'):
                yield item.wrapped()
            else:
                yield item

    def eager(self, *fields):
        qs = self._clone()
        field_set = set(fields)
        fk_fields = set(qs.model.get_fk_field_names()) & field_set
        m2m_fields = set(qs.model.get_m2m_field_names()) & field_set
        return qs.select_related(*fk_fields).prefetch_related(*m2m_fields)

    def sort(self, *fields):
        # Fields are passed in as e.g. [('title', 1), ('date_created', -1)]
        if isinstance(fields[0], list):
            fields = fields[0]

        def sort_key(item):
            if isinstance(item, basestring):
                return item
            elif isinstance(item, tuple):
                field_name, direction = item
                prefix = '-' if direction == -1 else ''
                return ''.join([prefix, field_name])

        sort_keys = [sort_key(each) for each in fields]
        return self.order_by(*sort_keys)

    def limit(self, n):
        return self[:n]


class BaseModel(models.Model):
    """Base model that acts makes subclasses mostly compatible with the
    modular-odm ``StoredObject`` interface.
    """

    migration_page_size = 50000

    objects = MODMCompatibilityQuerySet.as_manager()

    class Meta:
        abstract = True

    @classmethod
    def get_fk_field_names(cls):
        return [field.name for field in cls._meta.get_fields() if
                    field.is_relation and not field.auto_created and (field.many_to_one or field.one_to_one) and not isinstance(field, GenericForeignKey)]

    @classmethod
    def get_m2m_field_names(cls):
        return [field.attname or field.name for field in
                     cls._meta.get_fields() if
                     field.is_relation and field.many_to_many and not hasattr(field, 'field')]

    @classmethod
    def load(cls, data):
        try:
            if issubclass(cls, GuidMixin):
                return cls.objects.get(guids___id=data)
            elif issubclass(cls, ObjectIDMixin):
                return cls.objects.get(_id=data)
            elif isinstance(data, basestring):
                # Some models (CitationStyle) have an _id that is not a bson
                # Looking up things by pk will never work with a basestring
                return cls.objects.get(_id=data)
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None

    @classmethod
    def find_one(cls, query):
        try:
            return cls.objects.get(to_django_query(query, model_cls=cls))
        except cls.DoesNotExist:
            raise modularodm.exceptions.NoResultsFound()
        except cls.MultipleObjectsReturned as e:
            raise modularodm.exceptions.MultipleResultsFound(*e.args)

    @classmethod
    def find(cls, query=None):
        if not query:
            return cls.objects.all()
        else:
            return cls.objects.filter(to_django_query(query, model_cls=cls))

    @classmethod
    def remove(cls, query=None):
        return cls.find(query).delete()

    @classmethod
    def remove_one(cls, obj):
        if obj.pk:
            return obj.delete()

    @classmethod
    def migrate_from_modm(cls, modm_obj):
        """
        Given a modm object, make a django object with the same local fields.

        This is a base method that may work for simple objects.
        It should be customized in the child class if it doesn't work.

        :param modm_obj:
        :return:
        """
        django_obj = cls()

        local_django_fields = set([x.name for x in django_obj._meta.get_fields() if not x.is_relation])

        intersecting_fields = set(modm_obj.to_storage().keys()).intersection(
            set(local_django_fields))

        for field in intersecting_fields:
            modm_value = getattr(modm_obj, field)
            if modm_value is None:
                continue
            if isinstance(modm_value, datetime):
                modm_value = pytz.utc.localize(modm_value)
            # TODO Remove this after migration
            if isinstance(django_obj._meta.get_field(field), DateTimeAwareJSONField):
                modm_value = coerce_nonnaive_datetimes(modm_value)
            setattr(django_obj, field, modm_value)

        return django_obj

    @property
    def _primary_name(self):
        return '_id'

    def reload(self):
        return self.refresh_from_db()

    def _natural_key(self):
        return self.pk

    def clone(self):
        """Create a new, unsaved copy of this object."""
        copy = self.__class__.objects.get(pk=self.pk)
        copy.id = None

        # empty all the fks
        fk_field_names = [f.name for f in self._meta.model._meta.get_fields() if isinstance(f, (ForeignKey, GenericForeignKey))]
        for field_name in fk_field_names:
            setattr(copy, field_name, None)

        try:
            copy._id = bson.ObjectId()
        except AttributeError:
            pass
        return copy

    def save(self, *args, **kwargs):
        # Make Django validate on save (like modm)
        if not kwargs.get('force_insert') and not kwargs.get('force_update'):
            try:
                self.full_clean()
            except DjangoValidationError as err:
                raise ValidationError(*err.args)
        return super(BaseModel, self).save(*args, **kwargs)


# TODO: Rename to Identifier?
class Guid(BaseModel):
    """Stores either a short guid or long object_id for any model that inherits from BaseIDMixin.
    Each ID field (e.g. 'guid', 'object_id') MUST have an accompanying method, named with
    'initialize_<ID type>' (e.g. 'initialize_guid') that generates and sets the field.
    """
    primary_identifier_name = '_id'
    # TODO DELETE ME POST MIGRATION
    modm_query = None
    migration_page_size = 500000
    # /TODO DELETE ME POST MIGRATION

    id = models.AutoField(primary_key=True)
    _id = LowercaseCharField(max_length=255, null=False, blank=False, default=generate_guid, db_index=True,
                           unique=True)
    referent = GenericForeignKey()
    content_type = models.ForeignKey(ContentType, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    created = NonNaiveDateTimeField(db_index=True, default=timezone.now)  # auto_now_add=True)

    # Override load in order to load by GUID
    @classmethod
    def load(cls, data):
        try:
            return cls.objects.get(_id=data)
        except cls.DoesNotExist:
            return None

    def reload(self):
        del self._referent_cache
        return super(Guid, self).reload()

    @classmethod
    def migrate_from_modm(cls, modm_obj, object_id=None, content_type=None):
        """
        Given a modm Guid make a django Guid

        :param object_id:
        :param content_type:
        :param modm_obj:
        :return:
        """
        django_obj = cls()

        if modm_obj._id != modm_obj.referent._id:
            # if the object has a BSON id, get the created date from that
            django_obj.created = bson.ObjectId(modm_obj.referent._id).generation_time
        else:
            # just make it now
            django_obj.created = timezone.now()

        django_obj._id = modm_obj._id

        if object_id and content_type:
            # if the referent was passed set the GFK to point to it
            django_obj.content_type = content_type
            django_obj.object_id = object_id

        return django_obj

    class Meta:
        ordering = ['-created']
        get_latest_by = 'created'
        index_together = (
            ('content_type', 'object_id', 'created'),
        )


class BlackListGuid(BaseModel):
    # TODO DELETE ME POST MIGRATION
    modm_model_path = 'framework.guid.model.BlacklistGuid'
    primary_identifier_name = 'guid'
    modm_query = None
    migration_page_size = 500000
    # /TODO DELETE ME POST MIGRATION
    id = models.AutoField(primary_key=True)
    guid = LowercaseCharField(max_length=255, unique=True, db_index=True)

    @property
    def _id(self):
        return self.guid

    @classmethod
    def migrate_from_modm(cls, modm_obj):
        """
        Given a modm BlacklistGuid make a django BlackListGuid

        :param modm_obj:
        :return:
        """
        django_obj = cls()

        django_obj.guid = modm_obj._id

        return django_obj


def generate_guid_instance():
    return Guid.objects.create().id


class PKIDStr(str):
    def __new__(self, _id, pk):
        return str.__new__(self, _id)

    def __init__(self, _id, pk):
        self.__pk = pk

    def __int__(self):
        return self.__pk


class BaseIDMixin(models.Model):
    @classmethod
    def migrate_from_modm(cls, modm_obj):
        """
        Given a modm object, make a django object with the same local fields.

        This is a base method that may work for simple objects.
        It should be customized in the child class if it doesn't work.

        :param modm_obj:
        :return:
        """
        django_obj = cls()

        local_django_fields = set([x.name for x in django_obj._meta.get_fields() if not x.is_relation])

        intersecting_fields = set(modm_obj.to_storage().keys()).intersection(
            set(local_django_fields))

        for field in intersecting_fields:
            modm_value = getattr(modm_obj, field)
            if modm_value is None:
                continue
            if isinstance(modm_value, datetime):
                modm_value = pytz.utc.localize(modm_value)
            # TODO Remove this after migration
            if isinstance(django_obj._meta.get_field(field), DateTimeAwareJSONField):
                modm_value = coerce_nonnaive_datetimes(modm_value)
            setattr(django_obj, field, modm_value)

        return django_obj

    class Meta:
        abstract = True


class ObjectIDMixin(BaseIDMixin):
    primary_identifier_name = '_id'

    _id = models.CharField(max_length=24, default=generate_object_id, unique=True, db_index=True)

    @classmethod
    def load(cls, q):
        try:
            return cls.objects.get(_id=q)
        except cls.DoesNotExist:
            # modm doesn't throw exceptions when loading things that don't exist
            return None

    @classmethod
    def migrate_from_modm(cls, modm_obj):
        django_obj = super(ObjectIDMixin, cls).migrate_from_modm(modm_obj)
        django_obj._id = str(modm_obj._id)
        return django_obj

    class Meta:
        abstract = True

    def _natural_key(self):
        return self._id


class InvalidGuid(Exception):
    pass


class OptionalGuidMixin(BaseIDMixin):
    """
    This makes it so that things can **optionally** have guids. Think files.
    Things that inherit from this must also inherit from ObjectIDMixin ... probably
    """
    __guid_min_length__ = 5

    guids = GenericRelation(Guid, related_name='referent', related_query_name='referents')
    guid_string = ArrayField(models.CharField(max_length=255, null=True, blank=True), null=True, blank=True)
    content_type_pk = models.PositiveIntegerField(null=True, blank=True)

    def get_guid(self, create=False):
        if create:
            try:
                guid, created = Guid.objects.get_or_create(
                    object_id=self.pk,
                    content_type_id=ContentType.objects.get_for_model(self).pk
                )
            except MultipleObjectsReturned:
                # lol, hacks
                pass
            else:
                return guid
        return self.guids.order_by('-created').first()

    @classmethod
    def migrate_from_modm(cls, modm_obj):
        instance = super(OptionalGuidMixin, cls).migrate_from_modm(modm_obj)
        from website.models import Guid as MODMGuid
        from modularodm import Q as MODMQ
        if modm_obj.get_guid():
            guids = MODMGuid.find(MODMQ('referent', 'eq', modm_obj._id))
            setattr(instance, 'guid_string', [x.lower() for x in guids.get_keys()])
            setattr(instance, 'content_type_pk', ContentType.objects.get_for_model(cls).pk)
        return instance

    class Meta:
        abstract = True


class GuidMixinQuerySet(MODMCompatibilityQuerySet):
    tables = ['osf_guid', 'django_content_type']

    GUID_FIELDS = [
        'guids__id',
        'guids___id',
        'guids__content_type_id',
        'guids__object_id',
        'guids__created'
    ]

    def safe_table_alias(self, table_name, create=False):
        """
        Returns a table alias for the given table_name and whether this is a
        new alias or not.

        If 'create' is true, a new alias is always created. Otherwise, the
        most recently created alias for the table (if one exists) is reused.
        """
        alias_list = self.query.table_map.get(table_name)
        if not create and alias_list:
            alias = alias_list[0]
            if alias in self.query.alias_refcount:
                self.query.alias_refcount[alias] += 1
            else:
                self.query.alias_refcount[alias] = 1
            return alias, False

        # Create a new alias for this table.
        if alias_list:
            alias = '%s%d' % (self.query.alias_prefix, len(self.query.alias_map) + 1)
            alias_list.append(alias)
        else:
            # The first occurrence of a table uses the table name directly.
            alias = table_name
            self.query.table_map[alias] = [alias]
        self.query.alias_refcount[alias] = 1
        self.tables.append(alias)
        return alias, True

    def annotate_query_with_guids(self):
        self._prefetch_related_lookups = ['guids']
        for field in self.GUID_FIELDS:
            self.query.add_annotation(
                F(field), '_{}'.format(field), is_summary=False
            )
        for table in self.tables:
            if table not in self.query.tables:
                self.safe_table_alias(table)

    def remove_guid_annotations(self):
        for k, v in self.query.annotations.iteritems():
            if k[1:] in self.GUID_FIELDS:
                del self.query.annotations[k]
        for table_name in ['osf_guid', 'django_content_type']:
            if table_name in self.query.alias_map:
                del self.query.alias_map[table_name]
            if table_name in self.query.alias_refcount:
                del self.query.alias_refcount[table_name]
            if table_name in self.query.tables:
                del self.query.tables[self.query.tables.index(table_name)]

    def _clone(self, annotate=False, **kwargs):
        query = self.query.clone()
        if self._sticky_filter:
            query.filter_is_sticky = True
        if annotate:
            self.annotate_query_with_guids()
        clone = self.__class__(model=self.model, query=query, using=self._db, hints=self._hints)
        # this method was copied from the default django queryset except for the below two lines
        if annotate:
            clone.annotate_query_with_guids()
        clone._for_write = self._for_write
        clone._prefetch_related_lookups = self._prefetch_related_lookups[:]
        clone._known_related_objects = self._known_related_objects
        clone._iterable_class = self._iterable_class
        clone._fields = self._fields

        clone.__dict__.update(kwargs)
        return clone

    def annotate(self, *args, **kwargs):
        self.annotate_query_with_guids()
        return super(GuidMixinQuerySet, self).annotate(*args, **kwargs)

    def _filter_or_exclude(self, negate, *args, **kwargs):
        if args or kwargs:
            assert self.query.can_filter(), \
                'Cannot filter a query once a slice has been taken.'
        clone = self._clone(annotate=True)
        if negate:
            clone.query.add_q(~Q(*args, **kwargs))
        else:
            clone.query.add_q(Q(*args, **kwargs))
        return clone

    def all(self):
        return self._clone(annotate=True)

    # does implicit filter
    def get(self, *args, **kwargs):
        # add this to make sure we don't get dupes
        self.query.add_distinct_fields('id')
        return super(GuidMixinQuerySet, self).get(*args, **kwargs)

    # TODO: Below lines are commented out to ensure that
    # the annotations are used after running .count()
    # e.g.
    #    queryset.count()
    #    queryset[0]
    # This is more efficient when doing chained operations
    # on a queryset, but less efficient when only getting a count.
    # Figure out a way to get the best of both worlds

    # def count(self):
    #     self.remove_guid_annotations()
    #     return super(GuidMixinQuerySet, self).count()

    def update(self, **kwargs):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).update(**kwargs)

    def update_or_create(self, defaults=None, **kwargs):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).update_or_create(defaults=defaults, **kwargs)

    def values(self, *fields):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).values(*fields)

    def create(self, **kwargs):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).create(**kwargs)

    def bulk_create(self, objs, batch_size=None):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).bulk_create(objs, batch_size)

    def get_or_create(self, defaults=None, **kwargs):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).get_or_create(defaults, **kwargs)

    def values_list(self, *fields, **kwargs):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).values_list(*fields, **kwargs)

    def exists(self):
        self.remove_guid_annotations()
        return super(GuidMixinQuerySet, self).exists()

    def _fetch_all(self):
        if self._result_cache is None:
            self._result_cache = list(self._iterable_class(self))
        if self._prefetch_related_lookups and not self._prefetch_done:
            if 'guids' in self._prefetch_related_lookups and self._result_cache and hasattr(self._result_cache[0], '_guids__id'):
                # if guids is requested for prefetch and there are things in the result cache and the first one has
                # the annotated guid fields then remove guids from prefetch_related_lookups
                del self._prefetch_related_lookups[self._prefetch_related_lookups.index('guids')]
                results = []
                for result in self._result_cache:
                    # loop through the result cache
                    guid_dict = {}
                    for field in self.GUID_FIELDS:
                        # pull the fields off of the result object and put them in a dictionary without prefixed names
                        guid_dict[field] = getattr(result, '_{}'.format(field), None)
                    if None in guid_dict.values():
                        # if we get an invalid result field value, stop
                        logger.warning(
                            'Annotated guids came back will None values for {}, resorting to extra query'.format(result))
                        return
                    if not hasattr(result, '_prefetched_objects_cache'):
                        # initialize _prefetched_objects_cache
                        result._prefetched_objects_cache = {}
                    if 'guids' not in result._prefetched_objects_cache:
                        # intialize guids in _prefetched_objects_cache
                        result._prefetched_objects_cache['guids'] = []
                    # build a result dictionary of even more proper fields
                    result_dict = {key.replace('guids__', ''): value for key, value in guid_dict.iteritems()}
                    # make an unsaved guid instance
                    guid = Guid(**result_dict)
                    result._prefetched_objects_cache['guids'].append(guid)
                    results.append(result)
                # replace the result cache with the new set of results
                self._result_cache = results
            self._prefetch_related_objects()


class GuidMixin(BaseIDMixin):
    __guid_min_length__ = 5

    primary_identifier_name = 'guid_string'

    guids = GenericRelation(Guid, related_name='referent', related_query_name='referents')
    guid_string = ArrayField(models.CharField(max_length=255, null=True, blank=True), null=True, blank=True)
    content_type_pk = models.PositiveIntegerField(null=True, blank=True)

    objects = GuidMixinQuerySet.as_manager()

    # TODO: use pre-delete signal to disable delete cascade

    def _natural_key(self):
        return self.guid_string

    @cached_property
    def _id(self):
        try:
            guid = self.guids.all()[0]
        except IndexError:
            return None
        if guid:
            return guid._id
        return None

    @_id.setter
    def _id(self, value):
        # TODO do we really want to allow this?
        guid, created = Guid.objects.get_or_create(_id=value)
        if created:
            guid.object_id = self.pk
            guid.content_type = ContentType.objects.get_for_model(self)
            guid.save()
        elif guid.content_type == ContentType.objects.get_for_model(self) and guid.object_id == self.pk:
            # TODO should this up the created for the guid until now so that it appears as the first guid
            # for this object?
            return
        else:
            raise InvalidGuid('Cannot indirectly repoint an existing guid, please use the Guid model')

    _primary_key = _id

    @classmethod
    def load(cls, q):
        try:
            return cls.objects.filter(guids___id=q)[0]
        except IndexError:
            # modm doesn't throw exceptions when loading things that don't exist
            return None

    @property
    def deep_url(self):
        return None

    @classmethod
    def migrate_from_modm(cls, modm_obj):
        """
        Given a modm object, make a django object with the same local fields.

        This is a base method that may work for simple objects.
        It should be customized in the child class if it doesn't work.

        :param modm_obj:
        :return:
        """
        django_obj = cls()

        local_django_fields = set(
            [x.name for x in django_obj._meta.get_fields() if not x.is_relation and x.name != '_id'])

        intersecting_fields = set(modm_obj.to_storage().keys()).intersection(
            set(local_django_fields))

        for field in intersecting_fields:
            modm_value = getattr(modm_obj, field)
            if modm_value is None:
                continue
            if isinstance(modm_value, datetime):
                modm_value = pytz.utc.localize(modm_value)
            # TODO Remove this after migration
            if isinstance(django_obj._meta.get_field(field), DateTimeAwareJSONField):
                modm_value = coerce_nonnaive_datetimes(modm_value)
            setattr(django_obj, field, modm_value)

        from website.models import Guid as MODMGuid
        from modularodm import Q as MODMQ

        guids = MODMGuid.find(MODMQ('referent', 'eq', modm_obj._id))

        setattr(django_obj, 'guid_string', list(set([x.lower() for x in guids.get_keys()])))
        setattr(django_obj, 'content_type_pk', ContentType.objects.get_for_model(cls).pk)

        return django_obj

    class Meta:
        abstract = True


@receiver(post_save)
def ensure_guid(sender, instance, created, **kwargs):
    if not issubclass(sender, GuidMixin):
        return False
    existing_guids = Guid.objects.filter(object_id=instance.pk, content_type=ContentType.objects.get_for_model(instance))
    has_cached_guids = hasattr(instance, '_prefetched_objects_cache') and 'guids' in instance._prefetched_objects_cache
    if not existing_guids.exists():
        # Clear query cache of instance.guids
        if has_cached_guids:
            del instance._prefetched_objects_cache['guids']
        Guid.objects.create(object_id=instance.pk, content_type=ContentType.objects.get_for_model(instance),
                            _id=generate_guid(instance.__guid_min_length__))
    elif not existing_guids.exists() and instance.guid_string is not None:
        # Clear query cache of instance.guids
        if has_cached_guids:
            del instance._prefetched_objects_cache['guids']
        Guid.objects.create(object_id=instance.pk, content_type_id=instance.content_type_pk,
                            _id=instance.guid_string)