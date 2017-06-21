from nose.tools import *  # flake8: noqa

from modularodm import Q
from tests.base import ApiTestCase
from osf_tests.factories import SubjectFactory
from osf.models import Subject
from api.base.settings.defaults import API_BASE


class TestTaxonomy(ApiTestCase):
    def setUp(self):
        super(TestTaxonomy, self).setUp()

        # Subject 1 has 3 children
        self.subject1 = SubjectFactory()
        self.subject1_child1 = SubjectFactory(parent=self.subject1)
        self.subject1_child2 = SubjectFactory(parent=self.subject1)

        self.subjects = Subject.find()
        self.url = '/{}taxonomies/'.format(API_BASE)
        self.res = self.app.get(self.url)
        self.data = self.res.json['data']

    def test_taxonomy_success(self):
        assert_greater(len(self.subjects), 0)  # make sure there are subjects to filter through
        assert_equal(self.res.status_code, 200)
        assert_equal(self.res.content_type, 'application/vnd.api+json')

    def test_taxonomy_text(self):
        for index, subject in enumerate(self.subjects):
            if index >= len(self.data):
                break  # only iterate though first page of results
            assert_equal(self.data[index]['attributes']['text'], subject.text)

    def test_taxonomy_parents(self):
        for index, subject in enumerate(self.subjects):
            if index >= len(self.data):
                break
            parents_ids = []
            for parent in self.data[index]['attributes']['parents']:
                parents_ids.append(parent['id'])
            if subject.parent:
                assert subject.parent._id in parents_ids

    def test_taxonomy_filter_top_level(self):
        top_level_subjects = Subject.objects.filter(parent__isnull=True)
        top_level_url = self.url + '?filter[parents]=null'

        res = self.app.get(top_level_url)
        assert_equal(res.status_code, 200)

        data = res.json['data']
        assert_equal(len(top_level_subjects), len(data))
        assert len(top_level_subjects) > 0
        for subject in data:
            assert_equal(subject['attributes']['parents'], [])

    def test_taxonomy_filter_by_parent(self):
        children_subjects = Subject.objects.filter(parent__id=self.subject1.id)
        children_url = self.url + '?filter[parents]={}'.format(self.subject1._id)

        res = self.app.get(children_url)
        assert_equal(res.status_code, 200)

        data = res.json['data']
        assert_equal(len(children_subjects), len(data))

        for subject in data:
            parents_ids = []
            for parent in subject['attributes']['parents']:
                parents_ids.append(parent['id'])
            assert_in(self.subject1._id, parents_ids)
