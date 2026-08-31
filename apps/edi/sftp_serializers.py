from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.edi.choices import SFTPAuthType, SFTPDirectoryPurpose
from apps.edi.models import SFTPCredentials, SFTPDirectory
from apps.edi.utils.validators import clean_optional_text
from apps.trading_partner.choices import Environment


SECRET_WRITE_ONLY = (
    "password",
    "private_key_pem",
    "private_key_passphrase",
)


def _normalize_remote_path(value, field_name):
    value = clean_optional_text(value)
    if not value:
        raise serializers.ValidationError(f"{field_name} is required.")
    if "\\" in value:
        raise serializers.ValidationError(
            f"{field_name} must use forward slashes, not backslashes."
        )
    if ".." in value.split("/"):
        raise serializers.ValidationError(
            f"{field_name} must not contain '..' path segments."
        )
    return value


class SFTPCredentialsSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    private_key_pem = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    private_key_passphrase = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    has_password = serializers.SerializerMethodField(read_only=True)
    has_private_key = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SFTPCredentials
        fields = (
            "id",
            "name",
            "trading_partner",
            "environment",
            "host",
            "port",
            "username",
            "auth_type",
            "password",
            "private_key_pem",
            "private_key_passphrase",
            "has_password",
            "has_private_key",
            "host_fingerprint",
            "timeout_seconds",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "has_password",
            "has_private_key",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(serializers.BooleanField())
    def get_has_password(self, obj):
        return bool(obj.password)

    @extend_schema_field(serializers.BooleanField())
    def get_has_private_key(self, obj):
        return bool(obj.private_key_pem)

    def validate_name(self, value):
        value = clean_optional_text(value)
        if not value:
            raise serializers.ValidationError("name is required.")
        return value

    def validate_host(self, value):
        value = clean_optional_text(value)
        if not value:
            raise serializers.ValidationError("host is required.")
        return value

    def validate_username(self, value):
        value = clean_optional_text(value)
        if not value:
            raise serializers.ValidationError("username is required.")
        return value

    def validate_port(self, value):
        if value is None:
            return 22
        if int(value) < 1 or int(value) > 65535:
            raise serializers.ValidationError("port must be between 1 and 65535.")
        return int(value)

    def validate_timeout_seconds(self, value):
        if value is None:
            return 30
        if int(value) < 1 or int(value) > 600:
            raise serializers.ValidationError(
                "timeout_seconds must be between 1 and 600."
            )
        return int(value)

    def validate_environment(self, value):
        if value in (None, ""):
            return Environment.TEST
        value = str(value).strip().upper()
        if value not in Environment.values:
            raise serializers.ValidationError("Invalid environment.")
        return value

    def validate_auth_type(self, value):
        if value in (None, ""):
            return SFTPAuthType.PASSWORD
        value = str(value).strip().upper()
        if value not in SFTPAuthType.values:
            raise serializers.ValidationError("Invalid auth_type.")
        return value

    def validate_trading_partner(self, value):
        if value is None:
            return value
        if not value.is_active:
            raise serializers.ValidationError(
                "Trading partner not found or inactive."
            )
        return value

    def validate_notes(self, value):
        return clean_optional_text(value)

    def validate_host_fingerprint(self, value):
        return clean_optional_text(value)

    def validate_password(self, value):
        return clean_optional_text(value)

    def validate_private_key_pem(self, value):
        return clean_optional_text(value)

    def validate_private_key_passphrase(self, value):
        return clean_optional_text(value)

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", None))
        environment = attrs.get(
            "environment", getattr(self.instance, "environment", Environment.TEST)
        )
        if name and environment:
            qs = SFTPCredentials.objects.filter(
                name__iexact=name, environment=environment
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"name": ["This name already exists for the environment."]}
                )

        auth_type = attrs.get(
            "auth_type",
            getattr(self.instance, "auth_type", SFTPAuthType.PASSWORD),
        )
        password = attrs.get("password", getattr(self.instance, "password", None))
        private_key = attrs.get(
            "private_key_pem", getattr(self.instance, "private_key_pem", None)
        )

        # On create, secrets must match auth_type.
        if self.instance is None:
            if auth_type == SFTPAuthType.PASSWORD and not password:
                raise serializers.ValidationError(
                    {"password": ["password is required for PASSWORD auth."]}
                )
            if auth_type == SFTPAuthType.PRIVATE_KEY and not private_key:
                raise serializers.ValidationError(
                    {
                        "private_key_pem": [
                            "private_key_pem is required for PRIVATE_KEY auth."
                        ]
                    }
                )
            if auth_type == SFTPAuthType.PASSWORD_AND_KEY and (
                not password or not private_key
            ):
                raise serializers.ValidationError(
                    "password and private_key_pem are required for PASSWORD_AND_KEY."
                )
        else:
            # Partial update: if auth_type changes, ensure resulting secrets exist.
            if "auth_type" in attrs or "password" in attrs or "private_key_pem" in attrs:
                if auth_type == SFTPAuthType.PASSWORD and not password:
                    raise serializers.ValidationError(
                        {"password": ["password is required for PASSWORD auth."]}
                    )
                if auth_type == SFTPAuthType.PRIVATE_KEY and not private_key:
                    raise serializers.ValidationError(
                        {
                            "private_key_pem": [
                                "private_key_pem is required for PRIVATE_KEY auth."
                            ]
                        }
                    )
                if auth_type == SFTPAuthType.PASSWORD_AND_KEY and (
                    not password or not private_key
                ):
                    raise serializers.ValidationError(
                        "password and private_key_pem are required for PASSWORD_AND_KEY."
                    )
        return attrs

    def create(self, validated_data):
        from apps.core.crypto_secrets import encrypt_secret

        for field in SECRET_WRITE_ONLY:
            if field in validated_data and validated_data[field]:
                validated_data[field] = encrypt_secret(validated_data[field])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        from apps.core.crypto_secrets import encrypt_secret

        # Omit blank secret fields so PATCH without password does not clear it.
        for field in SECRET_WRITE_ONLY:
            if field in validated_data and validated_data[field] in (None, ""):
                validated_data.pop(field)
            elif field in validated_data and validated_data[field]:
                validated_data[field] = encrypt_secret(validated_data[field])
        return super().update(instance, validated_data)


class SFTPCredentialsListSerializer(serializers.ModelSerializer):
    has_password = serializers.SerializerMethodField()
    has_private_key = serializers.SerializerMethodField()

    class Meta:
        model = SFTPCredentials
        fields = (
            "id",
            "name",
            "trading_partner",
            "environment",
            "host",
            "port",
            "username",
            "auth_type",
            "has_password",
            "has_private_key",
            "timeout_seconds",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_has_password(self, obj):
        return bool(obj.password)

    @extend_schema_field(serializers.BooleanField())
    def get_has_private_key(self, obj):
        return bool(obj.private_key_pem)


class SFTPCredentialsIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)


class SFTPDirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SFTPDirectory
        fields = (
            "id",
            "credentials",
            "name",
            "purpose",
            "sending_path",
            "receiving_path",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        return clean_optional_text(value)

    def validate_purpose(self, value):
        if value in (None, ""):
            return SFTPDirectoryPurpose.GENERAL
        value = str(value).strip().upper()
        if value not in SFTPDirectoryPurpose.values:
            raise serializers.ValidationError("Invalid purpose.")
        return value

    def validate_sending_path(self, value):
        return _normalize_remote_path(value, "sending_path")

    def validate_receiving_path(self, value):
        return _normalize_remote_path(value, "receiving_path")

    def validate_credentials(self, value):
        if value is None:
            raise serializers.ValidationError("credentials is required.")
        if not value.is_active:
            raise serializers.ValidationError(
                "SFTP credentials not found or inactive."
            )
        return value

    def validate(self, attrs):
        credentials = attrs.get(
            "credentials", getattr(self.instance, "credentials", None)
        )
        purpose = attrs.get(
            "purpose",
            getattr(self.instance, "purpose", SFTPDirectoryPurpose.GENERAL),
        )
        sending_path = attrs.get(
            "sending_path", getattr(self.instance, "sending_path", None)
        )
        receiving_path = attrs.get(
            "receiving_path", getattr(self.instance, "receiving_path", None)
        )
        is_active = attrs.get(
            "is_active", getattr(self.instance, "is_active", True)
        )
        if credentials and sending_path and receiving_path and is_active:
            qs = SFTPDirectory.objects.filter(
                credentials=credentials,
                purpose=purpose,
                sending_path=sending_path,
                receiving_path=receiving_path,
                is_active=True,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "An active directory with these paths already exists."
                )
        return attrs


class SFTPDirectoryListSerializer(serializers.ModelSerializer):
    credentials_name = serializers.SerializerMethodField()

    class Meta:
        model = SFTPDirectory
        fields = (
            "id",
            "credentials",
            "credentials_name",
            "name",
            "purpose",
            "sending_path",
            "receiving_path",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_credentials_name(self, obj):
        return obj.credentials.name if obj.credentials_id else None


class SFTPDirectoryIdSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
