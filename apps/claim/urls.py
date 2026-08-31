from django.urls import path

from apps.claim.attachment_views import (
    AttachmentSubmissionDetailAPIView,
    AttachmentSubmissionListCreateAPIView,
)
from apps.claim.batch_views import (
    BatchClaimDetailAPIView,
    BatchClaimListCreateAPIView,
    SubmissionBatchAddClaimAPIView,
    SubmissionBatchDetailAPIView,
    SubmissionBatchListCreateAPIView,
)
from apps.claim.document_views import (
    ClaimDocumentDetailAPIView,
    ClaimDocumentListCreateAPIView,
    ClaimDocumentStatusAPIView,
)
from apps.claim.views import (
    ClaimDetailAPIView,
    ClaimFromTripAPIView,
    ClaimListCreateAPIView,
)

urlpatterns = [
    path("claims/", ClaimListCreateAPIView.as_view(), name="claim-list-create"),
    path(
        "claims/from-trip/",
        ClaimFromTripAPIView.as_view(),
        name="claim-from-trip",
    ),
    path(
        "claims/<int:pk>/document-status/",
        ClaimDocumentStatusAPIView.as_view(),
        name="claim-document-status",
    ),
    path("claims/<int:pk>/", ClaimDetailAPIView.as_view(), name="claim-detail"),
    path(
        "claim-documents/",
        ClaimDocumentListCreateAPIView.as_view(),
        name="claim-document-list-create",
    ),
    path(
        "claim-documents/<int:pk>/",
        ClaimDocumentDetailAPIView.as_view(),
        name="claim-document-detail",
    ),
    path(
        "attachment-submissions/",
        AttachmentSubmissionListCreateAPIView.as_view(),
        name="attachment-submission-list-create",
    ),
    path(
        "attachment-submissions/<int:pk>/",
        AttachmentSubmissionDetailAPIView.as_view(),
        name="attachment-submission-detail",
    ),
    path(
        "submission-batches/",
        SubmissionBatchListCreateAPIView.as_view(),
        name="submission-batch-list-create",
    ),
    path(
        "submission-batches/<int:pk>/add-claim/",
        SubmissionBatchAddClaimAPIView.as_view(),
        name="submission-batch-add-claim",
    ),
    path(
        "submission-batches/<int:pk>/",
        SubmissionBatchDetailAPIView.as_view(),
        name="submission-batch-detail",
    ),
    path(
        "batch-claims/",
        BatchClaimListCreateAPIView.as_view(),
        name="batch-claim-list-create",
    ),
    path(
        "batch-claims/<int:pk>/",
        BatchClaimDetailAPIView.as_view(),
        name="batch-claim-detail",
    ),
]
