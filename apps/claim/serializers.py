from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.claim.choices import (
    AttachmentRoute,
    AttachmentStatus,
    AttachmentSubmissionStatus,
    BatchStatus,
    ClaimStatus,
    DocumentStatus,
    DocumentType,
)
from apps.claim.models import (
    AttachmentSubmission,
    BatchClaim,
    Claim,
    ClaimDocument,
    SubmissionBatch,
)
from apps.claim.utils.validators import clean_optional_text, ensure_non_negative
from apps.trading_partner.choices import Environment
from apps.trading_partner.models import TradingPartner


class ClaimSerializer(serializers.ModelSerializer):
    trip_label = serializers.SerializerMethodField(read_only=True)
    patient_id = serializers.SerializerMethodField(read_only=True)
    provider_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Claim
        fields = (
            "id",
            "claim_number",
            "external_id",
            "trip",
            "trip_label",
            "patient_id",
            "provider_id",
            "diagnosis_code",
            "place_of_service",
            "total_charge",
            "status",
            "attachment_required",
            "attachment_route",
            "attachment_status",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "trip_label",
            "patient_id",
            "provider_id",
            "status",
            "attachment_required",
            "attachment_status",
            "is_active",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_trip_label(self, obj):
        if not obj.trip_id:
            return None
        return str(obj.trip)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_patient_id(self, obj):
        return obj.trip.patient_id if obj.trip_id else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_provider_id(self, obj):
        return obj.trip.provider_id if obj.trip_id else None

    def validate_claim_number(self, value):
        return clean_optional_text(value)

    def validate_external_id(self, value):
        return clean_optional_text(value)

    def validate_diagnosis_code(self, value):
        return clean_optional_text(value)

    def validate_place_of_service(self, value):
        return clean_optional_text(value)

    def validate_total_charge(self, value):
        return ensure_non_negative(value, "total_charge")

    def validate_status(self, value):
        if value in (None, ""):
            return ClaimStatus.DRAFT
        value = str(value).strip().upper()
        if value not in ClaimStatus.values:
            raise serializers.ValidationError("Invalid claim status.")
        return value

    def validate_attachment_route(self, value):
        if value in (None, ""):
            return AttachmentRoute.NONE
        value = str(value).strip().upper()
        if value not in AttachmentRoute.values:
            raise serializers.ValidationError("Invalid attachment_route.")
        return value

    def validate_attachment_status(self, value):
        if value in (None, ""):
            return AttachmentStatus.NOT_REQUIRED
        value = str(value).strip().upper()
        if value not in AttachmentStatus.values:
            raise serializers.ValidationError("Invalid attachment_status.")
        return value

    def validate_trip(self, value):
        if value is None:
            return value
        if not value.is_active:
            raise serializers.ValidationError("Trip not found or inactive.")
        return value

    def validate(self, attrs):
        trip = attrs.get("trip", getattr(self.instance, "trip", None))
        if trip is not None:
            qs = Claim.objects.filter(trip_id=trip.pk)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"trip": ["A claim already exists for this trip."]}
                )

        claim_number = attrs.get(
            "claim_number", getattr(self.instance, "claim_number", None)
        )
        if claim_number:
            qs = Claim.objects.filter(claim_number__iexact=claim_number)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"claim_number": ["This claim_number already exists."]}
                )

        external_id = attrs.get(
            "external_id", getattr(self.instance, "external_id", None)
        )
        if external_id:
            qs = Claim.objects.filter(external_id__iexact=external_id)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"external_id": ["This external_id already exists."]}
                )
        return attrs


class ClaimListSerializer(serializers.ModelSerializer):
    patient_id = serializers.SerializerMethodField()
    provider_id = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = (
            "id",
            "claim_number",
            "external_id",
            "trip",
            "patient_id",
            "provider_id",
            "total_charge",
            "status",
            "attachment_required",
            "attachment_status",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_patient_id(self, obj):
        return obj.trip.patient_id if obj.trip_id else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_provider_id(self, obj):
        return obj.trip.provider_id if obj.trip_id else None


class ClaimIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class CreateClaimFromTripSerializer(serializers.Serializer):
    trip_id = serializers.IntegerField()
    claim_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    external_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    diagnosis_code = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    place_of_service = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default="41"
    )
    procedure_code = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default="A0100"
    )
    create_service_line = serializers.BooleanField(required=False, default=True)

    def validate_claim_number(self, value):
        return clean_optional_text(value)

    def validate_external_id(self, value):
        return clean_optional_text(value)

    def validate_diagnosis_code(self, value):
        return clean_optional_text(value)

    def validate_place_of_service(self, value):
        return clean_optional_text(value) or "41"

    def validate_procedure_code(self, value):
        return clean_optional_text(value) or "A0100"


class ClaimDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimDocument
        fields = (
            "id",
            "claim",
            "document_type",
            "file_name",
            "document_hash",
            "blob_ref",
            "content_type",
            "file_size",
            "is_signed",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "blob_ref",
            "content_type",
            "file_size",
            "created_at",
            "updated_at",
        )

    def validate_document_type(self, value):
        if value in (None, ""):
            raise serializers.ValidationError("document_type is required.")
        value = str(value).strip().upper()
        if value not in DocumentType.values:
            raise serializers.ValidationError("Invalid document_type.")
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return DocumentStatus.PENDING
        value = str(value).strip().upper()
        if value not in DocumentStatus.values:
            raise serializers.ValidationError("Invalid document status.")
        return value

    def validate_file_name(self, value):
        return clean_optional_text(value)

    def validate_document_hash(self, value):
        return clean_optional_text(value)

    def validate_claim(self, value):
        if value is None:
            raise serializers.ValidationError("claim is required.")
        if not value.is_active:
            raise serializers.ValidationError("Claim not found or inactive.")
        return value

    def validate(self, attrs):
        claim = attrs.get("claim", getattr(self.instance, "claim", None))
        document_type = attrs.get(
            "document_type", getattr(self.instance, "document_type", None)
        )
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        if claim and document_type and is_active:
            qs = ClaimDocument.objects.filter(
                claim_id=claim.pk,
                document_type=document_type,
                is_active=True,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "document_type": [
                            "An active document of this type already exists for the claim."
                        ]
                    }
                )
        return attrs


class ClaimDocumentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimDocument
        fields = (
            "id",
            "claim",
            "document_type",
            "file_name",
            "document_hash",
            "blob_ref",
            "file_size",
            "is_signed",
            "status",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class ClaimDocumentIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class ClaimDocumentUploadSerializer(serializers.Serializer):
    claim = serializers.IntegerField()
    document_type = serializers.CharField()
    file = serializers.FileField()
    is_signed = serializers.BooleanField(required=False, default=False)
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_document_type(self, value):
        value = str(value).strip().upper()
        if value not in DocumentType.values:
            raise serializers.ValidationError("Invalid document_type.")
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return DocumentStatus.COMPLETE
        value = str(value).strip().upper()
        if value not in DocumentStatus.values:
            raise serializers.ValidationError("Invalid document status.")
        return value


class AttachmentDashboardSerializer(serializers.Serializer):
    long_distance_claims = serializers.IntegerField()
    ready_with_documents = serializers.IntegerField()
    documents_complete = serializers.IntegerField()
    missing_verification = serializers.IntegerField()
    missing_trip_log = serializers.IntegerField()
    missing_signature = serializers.IntegerField()
    submitted = serializers.IntegerField()
    awaiting_confirmation = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    failed = serializers.IntegerField()
    blocked_from_batch = serializers.IntegerField()
    attachment_submissions_by_status = serializers.DictField(
        child=serializers.IntegerField()
    )


class SubmitAttachmentSerializer(serializers.Serializer):
    claim_id = serializers.IntegerField()
    channel = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    submission_reference = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    environment = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allow_retry = serializers.BooleanField(required=False, default=False)

    def validate_channel(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        value = value.upper()
        if value not in AttachmentRoute.values or value == AttachmentRoute.NONE:
            raise serializers.ValidationError("Invalid attachment channel.")
        return value

    def validate_environment(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        value = value.upper()
        if value not in Environment.values:
            raise serializers.ValidationError("Invalid environment.")
        return value

    def validate_submission_reference(self, value):
        return clean_optional_text(value)


class SubmissionBatchSerializer(serializers.ModelSerializer):
    trading_partner = serializers.PrimaryKeyRelatedField(
        queryset=TradingPartner.objects.filter(is_active=True),
        required=True,
        allow_null=False,
    )

    class Meta:
        model = SubmissionBatch
        fields = (
            "id",
            "batch_number",
            "trading_partner",
            "environment",
            "claim_count",
            "total_amount",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "claim_count",
            "total_amount",
            "created_at",
            "updated_at",
        )

    def validate_batch_number(self, value):
        value = clean_optional_text(value)
        if not value:
            raise serializers.ValidationError("batch_number is required.")
        return value

    def validate_environment(self, value):
        if value in (None, ""):
            return Environment.TEST
        value = str(value).strip().upper()
        if value not in Environment.values:
            raise serializers.ValidationError("Invalid environment.")
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return BatchStatus.DRAFT
        value = str(value).strip().upper()
        if value not in BatchStatus.values:
            raise serializers.ValidationError("Invalid batch status.")
        return value

    def validate_trading_partner(self, value):
        if value is None:
            raise serializers.ValidationError("trading_partner is required.")
        if not value.is_active:
            raise serializers.ValidationError(
                "Trading partner not found or inactive."
            )
        if not value.sender_id or not value.receiver_id:
            raise serializers.ValidationError(
                "Trading partner must have sender_id and receiver_id."
            )
        return value

    def validate(self, attrs):
        batch_number = attrs.get(
            "batch_number", getattr(self.instance, "batch_number", None)
        )
        if batch_number:
            qs = SubmissionBatch.objects.filter(batch_number__iexact=batch_number)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"batch_number": ["This batch_number already exists."]}
                )

        # On create, trading_partner is always required (field-level).
        # On partial update, block clearing it to null if sent.
        if self.instance is not None and "trading_partner" in attrs:
            if attrs.get("trading_partner") is None:
                raise serializers.ValidationError(
                    {"trading_partner": ["trading_partner cannot be cleared."]}
                )

        # Default batch environment from trading partner when omitted on create.
        partner = attrs.get("trading_partner")
        if partner is not None and "environment" not in attrs and self.instance is None:
            attrs["environment"] = partner.environment or Environment.TEST
        return attrs


class SubmissionBatchListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionBatch
        fields = (
            "id",
            "batch_number",
            "trading_partner",
            "environment",
            "claim_count",
            "total_amount",
            "status",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class SubmissionBatchIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class BatchClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = BatchClaim
        fields = (
            "id",
            "batch",
            "claim",
            "st02",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_st02(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        if not str(value).isdigit():
            raise serializers.ValidationError("st02 must be numeric.")
        return value.zfill(4) if len(value) <= 4 else value

    def validate_batch(self, value):
        if value is None:
            raise serializers.ValidationError("batch is required.")
        if not value.is_active:
            raise serializers.ValidationError("Batch not found or inactive.")
        return value

    def validate_claim(self, value):
        if value is None:
            raise serializers.ValidationError("claim is required.")
        if not value.is_active:
            raise serializers.ValidationError("Claim not found or inactive.")
        return value


class BatchClaimListSerializer(serializers.ModelSerializer):
    claim_number = serializers.SerializerMethodField()

    class Meta:
        model = BatchClaim
        fields = (
            "id",
            "batch",
            "claim",
            "claim_number",
            "st02",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_claim_number(self, obj):
        return obj.claim.claim_number if obj.claim_id else None


class BatchClaimIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class AddClaimToBatchSerializer(serializers.Serializer):
    claim_id = serializers.IntegerField()
    st02 = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_st02(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        if not str(value).isdigit():
            raise serializers.ValidationError("st02 must be numeric.")
        return value.zfill(4) if len(value) <= 4 else value


class AttachmentSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttachmentSubmission
        fields = (
            "id",
            "claim",
            "channel",
            "submission_reference",
            "payload_hash",
            "remote_path",
            "retry_count",
            "status",
            "submitted_at",
            "confirmed_at",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "payload_hash",
            "remote_path",
            "retry_count",
            "created_at",
            "updated_at",
        )

    def validate_channel(self, value):
        if value in (None, ""):
            return AttachmentRoute.HCPF_PORTAL
        value = str(value).strip().upper()
        if value not in AttachmentRoute.values:
            raise serializers.ValidationError("Invalid channel.")
        if value == AttachmentRoute.NONE:
            raise serializers.ValidationError(
                "channel cannot be NONE for an attachment submission."
            )
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return AttachmentSubmissionStatus.QUEUED
        value = str(value).strip().upper()
        if value not in AttachmentSubmissionStatus.values:
            raise serializers.ValidationError("Invalid attachment submission status.")
        return value

    def validate_submission_reference(self, value):
        return clean_optional_text(value)

    def validate_notes(self, value):
        return clean_optional_text(value)

    def validate_claim(self, value):
        if value is None:
            raise serializers.ValidationError("claim is required.")
        if not value.is_active:
            raise serializers.ValidationError("Claim not found or inactive.")
        if not value.attachment_required:
            raise serializers.ValidationError(
                "Claim does not require attachments (attachment_required=False)."
            )
        return value

    def validate(self, attrs):
        from apps.claim.utils.attachment_service import (
            ACTIVE_TRANSMISSION_STATUSES,
            assert_no_duplicate_attachment_submission,
            compute_claim_document_payload_hash,
        )

        claim = attrs.get("claim", getattr(self.instance, "claim", None))
        status = attrs.get("status", getattr(self.instance, "status", None))
        if claim and status in ACTIVE_TRANSMISSION_STATUSES:
            payload_hash = compute_claim_document_payload_hash(claim.id)
            if payload_hash:
                attrs["payload_hash"] = payload_hash
                if self.instance is None:
                    try:
                        assert_no_duplicate_attachment_submission(
                            claim.id, payload_hash
                        )
                    except ValueError as exc:
                        raise serializers.ValidationError({"claim": [str(exc)]})
        return attrs

    def create(self, validated_data):
        from apps.claim.utils.attachment_service import compute_claim_document_payload_hash

        claim = validated_data.get("claim")
        if claim and not validated_data.get("payload_hash"):
            validated_data["payload_hash"] = compute_claim_document_payload_hash(claim.id)
        return super().create(validated_data)


class AttachmentSubmissionListSerializer(serializers.ModelSerializer):
    claim_number = serializers.SerializerMethodField()

    class Meta:
        model = AttachmentSubmission
        fields = (
            "id",
            "claim",
            "claim_number",
            "channel",
            "submission_reference",
            "payload_hash",
            "remote_path",
            "status",
            "submitted_at",
            "confirmed_at",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_claim_number(self, obj):
        return obj.claim.claim_number if obj.claim_id else None


class AttachmentSubmissionIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)

