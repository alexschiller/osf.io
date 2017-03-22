from rest_framework import generics, permissions as drf_permissions
from framework.auth.oauth_scopes import CoreScopes

from api.base.filters import ODMFilterMixin
from api.base import permissions as base_permissions
from api.base.utils import get_object_or_error
from api.licenses.serializers import LicenseSerializer
from api.base.views import JSONAPIBaseView

from website.project.licenses import NodeLicense


class LicenseDetail(JSONAPIBaseView, generics.RetrieveAPIView):
    """The documentation for this endpoint can be found [here](https://developer.osf.io/#Licenses_licenses_read).
    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.LICENSE_READ]
    required_write_scopes = [CoreScopes.NULL]

    serializer_class = LicenseSerializer
    view_category = 'licenses'
    view_name = 'license-detail'
    lookup_url_kwarg = 'license_id'

    # overrides RetrieveAPIView
    def get_object(self):
        license = get_object_or_error(
            NodeLicense,
            self.kwargs[self.lookup_url_kwarg],
            display_name='license'
        )
        self.check_object_permissions(self.request, license)
        return license


class LicenseList(JSONAPIBaseView, generics.ListAPIView, ODMFilterMixin):
    """The documentation for this endpoint can be found [here](https://developer.osf.io/#Licenses_license_list).
    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.LICENSE_READ]
    required_write_scopes = [CoreScopes.NULL]

    serializer_class = LicenseSerializer
    view_category = 'licenses'
    view_name = 'license-list'

    ordering = ('name', )  # default ordering

    # overrides ODMFilterMixin
    def get_default_odm_query(self):
        base_query = None
        return base_query

    def get_queryset(self):
        queryset = NodeLicense.find(self.get_query_from_request())
        return queryset
