"""Unit tests for soft-delete / safe client error helpers."""

from django.http import Http404
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model

from apps.core.soft_delete import (
    client_error_message,
    get_active_object_or_404,
    get_api_object_or_404,
)
from apps.trading_partner.models import TradingPartner

User = get_user_model()


class ClientErrorMessageTests(SimpleTestCase):
    def test_keeps_value_error_text(self):
        self.assertEqual(
            client_error_message(ValueError("Batch has no claims.")),
            "Batch has no claims.",
        )

    def test_strips_traceback_payload(self):
        payload = (
            "Traceback (most recent call last):\n"
            '  File "x.py", line 1, in <module>\n'
            "ValueError: boom"
        )
        self.assertEqual(client_error_message(Exception(payload)), "Request failed.")


class ActiveObjectLookupTests(TestCase):
    def test_active_only_hides_inactive(self):
        partner = TradingPartner.objects.create(
            name="TP",
            sender_id="S1",
            receiver_id="R1",
            environment="TEST",
            is_active=False,
        )
        with self.assertRaises(Http404):
            get_active_object_or_404(TradingPartner, pk=partner.pk)

        found = get_api_object_or_404(TradingPartner, pk=partner.pk, hard=True)
        self.assertEqual(found.pk, partner.pk)
