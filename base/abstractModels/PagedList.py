from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class PagedList(PageNumberPagination):
    """ A customised DRF's paginator """

    page_size_query_param = "page_size"  # Optionally allow the client to override the default page size

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "pageSize": self.get_page_size(self.request),  # Return the current page size
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data
        })
