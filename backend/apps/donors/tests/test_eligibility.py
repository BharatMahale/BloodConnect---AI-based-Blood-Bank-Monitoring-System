from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.donors.models import (
    DonorEligibilityAssessment,
    DonorProfile,
)
from apps.donors.services.eligibility import (
    assess_donor_eligibility,
)
from apps.inventory.models import BloodGroup


User = get_user_model()


class DonorEligibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="donor@example.com",
            password="Donor@12345",
        )

        self.blood_group = BloodGroup.objects.create(
            name="O Positive",
        )

        self.donor = DonorProfile.objects.create(
            user=self.user,
            blood_group=self.blood_group,
            date_of_birth=date.today().replace(
                year=date.today().year - 25,
            ),
            gender=DonorProfile.Gender.MALE,
            weight_kg=Decimal("65.00"),
            phone="9876543210",
            address="Shirpur",
            city="Shirpur",
            state="Maharashtra",
            pincode="425405",
            latitude=Decimal("21.349500"),
            longitude=Decimal("74.880200"),
            is_available=True,
            medical_declaration_accepted=True,
        )

        self.valid_answers = {
            "feeling_well": True,
            "has_fever_or_infection": False,
            "taking_antibiotics": False,
            "recent_surgery": False,
            "pregnant_or_breastfeeding": False,
            "recent_tattoo_or_piercing": False,
        }

    def test_healthy_donor_is_eligible(self):
        assessment = assess_donor_eligibility(
            donor=self.donor,
            answers=self.valid_answers,
        )

        self.assertTrue(assessment.is_eligible)
        self.assertEqual(assessment.reasons, [])

    def test_assessment_is_saved_in_database(self):
        assess_donor_eligibility(
            donor=self.donor,
            answers=self.valid_answers,
        )

        self.assertEqual(
            DonorEligibilityAssessment.objects.count(),
            1,
        )

    def test_underage_donor_is_not_eligible(self):
        self.donor.date_of_birth = date.today().replace(
            year=date.today().year - 17,
        )
        self.donor.save(
            update_fields=["date_of_birth"]
        )

        assessment = assess_donor_eligibility(
            donor=self.donor,
            answers=self.valid_answers,
        )

        self.assertFalse(assessment.is_eligible)
        self.assertTrue(
            any(
                "at least 18" in reason
                for reason in assessment.reasons
            )
        )

    def test_low_weight_donor_is_not_eligible(self):
        self.donor.weight_kg = Decimal("40.00")
        self.donor.save(
            update_fields=["weight_kg"]
        )

        assessment = assess_donor_eligibility(
            donor=self.donor,
            answers=self.valid_answers,
        )

        self.assertFalse(assessment.is_eligible)
        self.assertTrue(
            any(
                "at least 45" in reason
                for reason in assessment.reasons
            )
        )

    def test_recent_donation_makes_donor_ineligible(self):
        self.donor.last_donation_date = (
            date.today() - timedelta(days=20)
        )
        self.donor.save(
            update_fields=["last_donation_date"]
        )

        assessment = assess_donor_eligibility(
            donor=self.donor,
            answers=self.valid_answers,
        )

        self.assertFalse(assessment.is_eligible)
        self.assertTrue(
            any(
                "interval" in reason.lower()
                for reason in assessment.reasons
            )
        )

    def test_unwell_donor_is_not_eligible(self):
        answers = self.valid_answers.copy()
        answers["feeling_well"] = False

        assessment = assess_donor_eligibility(
            donor=self.donor,
            answers=answers,
        )

        self.assertFalse(assessment.is_eligible)