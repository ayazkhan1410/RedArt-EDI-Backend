# Soft-delete-scoped unique constraints for Claim / BatchClaim.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("claim", "0003_edi_ack_and_attachment_submission"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="claim",
            name="uniq_claim_claim_number_not_null",
        ),
        migrations.RemoveConstraint(
            model_name="claim",
            name="uniq_claim_external_id_not_null",
        ),
        migrations.RemoveConstraint(
            model_name="claim",
            name="uniq_claim_trip_not_null",
        ),
        migrations.RemoveConstraint(
            model_name="batchclaim",
            name="uniq_batch_claim_pair",
        ),
        migrations.RemoveConstraint(
            model_name="batchclaim",
            name="uniq_batch_st02",
        ),
        migrations.AddConstraint(
            model_name="claim",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    claim_number__isnull=False,
                    is_active=True,
                ),
                fields=("claim_number",),
                name="uniq_claim_claim_number_not_null",
            ),
        ),
        migrations.AddConstraint(
            model_name="claim",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    external_id__isnull=False,
                    is_active=True,
                ),
                fields=("external_id",),
                name="uniq_claim_external_id_not_null",
            ),
        ),
        migrations.AddConstraint(
            model_name="claim",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    trip__isnull=False,
                    is_active=True,
                ),
                fields=("trip",),
                name="uniq_claim_trip_not_null",
            ),
        ),
        migrations.AddConstraint(
            model_name="batchclaim",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    batch__isnull=False,
                    claim__isnull=False,
                    is_active=True,
                ),
                fields=("batch", "claim"),
                name="uniq_batch_claim_pair",
            ),
        ),
        migrations.AddConstraint(
            model_name="batchclaim",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    batch__isnull=False,
                    st02__isnull=False,
                    is_active=True,
                ),
                fields=("batch", "st02"),
                name="uniq_batch_st02",
            ),
        ),
    ]
