from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.edi.choices import (
    AcknowledgementStatus,
    AcknowledgementType,
    EDIFileStatus,
    TransactionType,
)
from apps.edi.models import (
    EDIAcknowledgement,
    EDIControlNumber,
    EDIFile,
    EDIFileTransferLog,
)
from apps.edi.utils.validators import clean_control_digits, clean_optional_text
from apps.trading_partner.choices import Environment


class EDIControlNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = EDIControlNumber
        fields = (
            "id",
            "batch",
            "environment",
            "isa13",
            "gs06",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_environment(self, value):
        if value in (None, ""):
            return Environment.TEST
        value = str(value).strip().upper()
        if value not in Environment.values:
            raise serializers.ValidationError("Invalid environment.")
        return value

    def validate_isa13(self, value):
        return clean_control_digits(value, "isa13", max_length=9, pad_to=9)

    def validate_gs06(self, value):
        return clean_control_digits(value, "gs06", max_length=9)

    def validate_batch(self, value):
        if value is None:
            raise serializers.ValidationError("batch is required.")
        if not value.is_active:
            raise serializers.ValidationError("Batch not found or inactive.")
        return value

    def validate(self, attrs):
        batch = attrs.get("batch", getattr(self.instance, "batch", None))
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        if batch and is_active:
            qs = EDIControlNumber.objects.filter(batch_id=batch.pk, is_active=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"batch": ["An active control-number record already exists for this batch."]}
                )
        return attrs


class EDIControlNumberListSerializer(serializers.ModelSerializer):
    batch_number = serializers.SerializerMethodField()

    class Meta:
        model = EDIControlNumber
        fields = (
            "id",
            "batch",
            "batch_number",
            "environment",
            "isa13",
            "gs06",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_batch_number(self, obj):
        return obj.batch.batch_number if obj.batch_id else None


class EDIControlNumberIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class AllocateControlNumberSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    environment = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    isa13 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    gs06 = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_environment(self, value):
        if value in (None, ""):
            return None
        value = str(value).strip().upper()
        if value not in Environment.values:
            raise serializers.ValidationError("Invalid environment.")
        return value

    def validate_isa13(self, value):
        return clean_control_digits(value, "isa13", max_length=9, pad_to=9)

    def validate_gs06(self, value):
        return clean_control_digits(value, "gs06", max_length=9)


class EDIFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EDIFile
        fields = (
            "id",
            "batch",
            "control_number",
            "transaction_type",
            "filename",
            "file_hash",
            "path_or_blob_ref",
            "status",
            "uploaded_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_transaction_type(self, value):
        if value in (None, ""):
            return TransactionType.X837P
        value = str(value).strip().upper()
        if value not in TransactionType.values:
            raise serializers.ValidationError("Invalid transaction_type.")
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return EDIFileStatus.GENERATED
        value = str(value).strip().upper()
        if value not in EDIFileStatus.values:
            raise serializers.ValidationError("Invalid EDI file status.")
        return value

    def validate_filename(self, value):
        return clean_optional_text(value)

    def validate_file_hash(self, value):
        return clean_optional_text(value)

    def validate_path_or_blob_ref(self, value):
        return clean_optional_text(value)

    def validate_batch(self, value):
        if value is None:
            raise serializers.ValidationError("batch is required.")
        if not value.is_active:
            raise serializers.ValidationError("Batch not found or inactive.")
        return value

    def validate(self, attrs):
        filename = attrs.get("filename", getattr(self.instance, "filename", None))
        if filename:
            qs = EDIFile.objects.filter(filename=filename)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"filename": ["This filename already exists."]}
                )
        return attrs


class EDIFileListSerializer(serializers.ModelSerializer):
    batch_number = serializers.SerializerMethodField()

    class Meta:
        model = EDIFile
        fields = (
            "id",
            "batch",
            "batch_number",
            "control_number",
            "transaction_type",
            "filename",
            "file_hash",
            "status",
            "uploaded_at",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_batch_number(self, obj):
        return obj.batch.batch_number if obj.batch_id else None


class EDIFileIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class CreateEDIFileFromBatchSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    transaction_type = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default="837P"
    )
    filename = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    file_hash = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    path_or_blob_ref = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allocate_controls = serializers.BooleanField(required=False, default=True)

    def validate_transaction_type(self, value):
        if value in (None, ""):
            return TransactionType.X837P
        value = str(value).strip().upper()
        if value not in TransactionType.values:
            raise serializers.ValidationError("Invalid transaction_type.")
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return EDIFileStatus.GENERATED
        value = str(value).strip().upper()
        if value not in EDIFileStatus.values:
            raise serializers.ValidationError("Invalid EDI file status.")
        return value

    def validate_filename(self, value):
        return clean_optional_text(value)

    def validate_file_hash(self, value):
        return clean_optional_text(value)

    def validate_path_or_blob_ref(self, value):
        return clean_optional_text(value)


class MarkEDIFileUploadedSerializer(serializers.Serializer):
    path_or_blob_ref = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    file_hash = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_path_or_blob_ref(self, value):
        return clean_optional_text(value)

    def validate_file_hash(self, value):
        return clean_optional_text(value)


class Generate837PSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    allocate_controls = serializers.BooleanField(required=False, default=True)


class QueueEDIFileUploadSerializer(serializers.Serializer):
    credentials_id = serializers.IntegerField(required=False, allow_null=True)


class EDIFileTransferLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EDIFileTransferLog
        fields = (
            "id",
            "edi_file",
            "channel",
            "status",
            "attempt",
            "remote_path",
            "message",
            "detail",
            "celery_task_id",
            "started_at",
            "finished_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class EDIFileTransferLogListSerializer(serializers.ModelSerializer):
    filename = serializers.SerializerMethodField()

    class Meta:
        model = EDIFileTransferLog
        fields = (
            "id",
            "edi_file",
            "filename",
            "channel",
            "status",
            "attempt",
            "remote_path",
            "message",
            "celery_task_id",
            "started_at",
            "finished_at",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_filename(self, obj):
        return obj.edi_file.filename if obj.edi_file_id else None


class EDIAcknowledgementSerializer(serializers.ModelSerializer):
    class Meta:
        model = EDIAcknowledgement
        fields = (
            "id",
            "batch",
            "edi_file",
            "ack_type",
            "status",
            "affected_st02",
            "raw_file_ref",
            "message",
            "acknowledged_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_ack_type(self, value):
        if value in (None, ""):
            return AcknowledgementType.X999
        value = str(value).strip().upper()
        if value not in AcknowledgementType.values:
            raise serializers.ValidationError("Invalid ack_type.")
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return AcknowledgementStatus.ACCEPTED
        value = str(value).strip().upper()
        if value not in AcknowledgementStatus.values:
            raise serializers.ValidationError("Invalid acknowledgement status.")
        return value

    def validate_affected_st02(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        if value.isdigit():
            return value.zfill(4) if len(value) <= 4 else value
        return value

    def validate_raw_file_ref(self, value):
        return clean_optional_text(value)

    def validate_message(self, value):
        return clean_optional_text(value)

    def validate_batch(self, value):
        if value is None:
            raise serializers.ValidationError("batch is required.")
        if not value.is_active:
            raise serializers.ValidationError("Batch not found or inactive.")
        return value

    def validate_edi_file(self, value):
        if value is None:
            return value
        if not value.is_active:
            raise serializers.ValidationError("EDI file not found or inactive.")
        return value

    def validate(self, attrs):
        batch = attrs.get("batch", getattr(self.instance, "batch", None))
        edi_file = attrs.get("edi_file", getattr(self.instance, "edi_file", None))
        if batch and edi_file and edi_file.batch_id and edi_file.batch_id != batch.pk:
            raise serializers.ValidationError(
                {"edi_file": ["EDI file must belong to the same batch."]}
            )
        return attrs


class EDIAcknowledgementListSerializer(serializers.ModelSerializer):
    batch_number = serializers.SerializerMethodField()

    class Meta:
        model = EDIAcknowledgement
        fields = (
            "id",
            "batch",
            "batch_number",
            "edi_file",
            "ack_type",
            "status",
            "affected_st02",
            "raw_file_ref",
            "acknowledged_at",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_batch_number(self, obj):
        return obj.batch.batch_number if obj.batch_id else None


class EDIAcknowledgementIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class ApplyEDIAcknowledgementSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    ack_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    affected_st02 = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    raw_file_ref = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    edi_file_id = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    apply_claim_status = serializers.BooleanField(required=False, default=True)

    def validate_ack_type(self, value):
        if value in (None, ""):
            return AcknowledgementType.X999
        value = str(value).strip().upper()
        if value not in AcknowledgementType.values:
            raise serializers.ValidationError("Invalid ack_type.")
        return value

    def validate_status(self, value):
        if value in (None, ""):
            return AcknowledgementStatus.ACCEPTED
        value = str(value).strip().upper()
        if value not in AcknowledgementStatus.values:
            raise serializers.ValidationError("Invalid acknowledgement status.")
        return value

    def validate_affected_st02(self, value):
        value = clean_optional_text(value)
        if value is None:
            return value
        if value.isdigit():
            return value.zfill(4) if len(value) <= 4 else value
        return value

    def validate_raw_file_ref(self, value):
        return clean_optional_text(value)

    def validate_message(self, value):
        return clean_optional_text(value)
