from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_page_size(self, request):
        raw = request.query_params.get(self.page_size_query_param)
        if raw in (None, ""):
            return self.page_size
        if not str(raw).isdigit() or int(raw) < 1:
            raise ValidationError({"page_size": ["Must be a positive whole number."]})
        return min(int(raw), self.max_page_size)

    def get_page_number(self, request, paginator):
        raw = request.query_params.get(self.page_query_param, 1)
        if raw in (None, ""):
            return 1
        if not str(raw).isdigit() or int(raw) < 1:
            raise ValidationError({"page": ["Must be a positive whole number."]})
        return int(raw)
