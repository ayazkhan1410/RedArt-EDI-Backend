from django.urls import reverse
from rest_framework import status
from apps.core.testing import AuthAPITestCase

from apps.patient.models import Patient


class PatientAPITests(AuthAPITestCase):
    def test_create_list_filter_by_county_and_duplicate_medicaid_id(self):
        list_url = reverse("patient-list-create")
        create = self.client.post(
            list_url,
            {
                "first_name": "Ali",
                "last_name": "Khan",
                "date_of_birth": "1995-05-12",
                "medicaid_member_id": "m123456789",
                "county": "Denver",
                "email": "ali@example.com",
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        patient_id = create.data["data"]["id"]
        patient = Patient.objects.get(pk=patient_id)
        self.assertEqual(patient.medicaid_member_id, "M123456789")

        listed = self.client.get(list_url, {"county": "denver"})
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)

        dup = self.client.post(
            list_url,
            {
                "first_name": "Ali",
                "last_name": "Two",
                "date_of_birth": "1996-01-01",
                "medicaid_member_id": "M123456789",
                "county": "Denver",
            },
            format="json",
        )
        self.assertIn(
            dup.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
        )

    def test_future_dob_rejected(self):
        url = reverse("patient-list-create")
        response = self.client.post(
            url,
            {
                "first_name": "Future",
                "last_name": "Kid",
                "date_of_birth": "2999-01-01",
                "medicaid_member_id": "M999",
                "county": "Denver",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_first_name_rejected(self):
        url = reverse("patient-list-create")
        response = self.client.post(
            url,
            {
                "first_name": "   ",
                "last_name": "Khan",
                "date_of_birth": "1995-05-12",
                "medicaid_member_id": "MBLANK",
                "county": "Denver",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete(self):
        patient = Patient.objects.create(
            first_name="SAMPLE",
            last_name="Ali",
            date_of_birth="1990-01-01",
            medicaid_member_id="M555",
            county="Denver",
        )
        url = reverse("patient-detail", kwargs={"pk": patient.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        patient.refresh_from_db()
        self.assertFalse(patient.is_active)

    def test_invalid_page_size_rejected(self):
        url = reverse("patient-list-create")
        response = self.client.get(url, {"page_size": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_county(self):
        patient = Patient.objects.create(
            first_name="Omar",
            last_name="Hassan",
            date_of_birth="1992-01-15",
            medicaid_member_id="M777",
            county="Denver",
        )
        url = reverse("patient-detail", kwargs={"pk": patient.id})
        response = self.client.patch(url, {"county": "Aurora"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        patient.refresh_from_db()
        self.assertEqual(patient.county, "Aurora")

    def test_demographics_and_invalid_state(self):
        url = reverse("patient-list-create")
        created = self.client.post(
            url,
            {
                "first_name": "Ali",
                "last_name": "Khan",
                "date_of_birth": "1995-05-12",
                "gender": "m",
                "medicaid_member_id": "MDEM001",
                "county": "Denver",
                "address_line_1": "100 Main St",
                "city": "Denver",
                "state": "co",
                "zip": "80202",
                "phone": "3035550100",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        patient = Patient.objects.get(pk=created.data["data"]["id"])
        self.assertEqual(patient.gender, "M")
        self.assertEqual(patient.state, "CO")
        self.assertTrue(patient.has_837p_demographics())

        bad = self.client.post(
            url,
            {
                "first_name": "Bad",
                "last_name": "State",
                "date_of_birth": "1990-01-01",
                "medicaid_member_id": "MBADSTATE",
                "county": "Denver",
                "state": "COLORADO",
            },
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
