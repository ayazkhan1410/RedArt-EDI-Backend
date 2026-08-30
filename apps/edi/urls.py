from django.urls import path

from apps.edi.views import (
    EDIControlNumberAllocateAPIView,
    EDIControlNumberDetailAPIView,
    EDIControlNumberListCreateAPIView,
    EDIFileDetailAPIView,
    EDIFileFromBatchAPIView,
    EDIFileListCreateAPIView,
    EDIFileMarkUploadedAPIView,
)

urlpatterns = [
    path(
        "edi-control-numbers/",
        EDIControlNumberListCreateAPIView.as_view(),
        name="edi-control-number-list-create",
    ),
    path(
        "edi-control-numbers/allocate/",
        EDIControlNumberAllocateAPIView.as_view(),
        name="edi-control-number-allocate",
    ),
    path(
        "edi-control-numbers/<int:pk>/",
        EDIControlNumberDetailAPIView.as_view(),
        name="edi-control-number-detail",
    ),
    path(
        "edi-files/",
        EDIFileListCreateAPIView.as_view(),
        name="edi-file-list-create",
    ),
    path(
        "edi-files/from-batch/",
        EDIFileFromBatchAPIView.as_view(),
        name="edi-file-from-batch",
    ),
    path(
        "edi-files/<int:pk>/mark-uploaded/",
        EDIFileMarkUploadedAPIView.as_view(),
        name="edi-file-mark-uploaded",
    ),
    path(
        "edi-files/<int:pk>/",
        EDIFileDetailAPIView.as_view(),
        name="edi-file-detail",
    ),
]
