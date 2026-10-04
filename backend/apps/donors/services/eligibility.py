from datetime import date
from django.db import transaction
from apps.donors.models import DonorEligibilityAssessment


MINIMUM_AGE = 18
MAXIMUM_AGE = 65
MINIMUM_WEIGHT_KG = 45
MINIMUM_DONATION_INTERVAL_DAYS = 90


def calculate_age(date_of_birth):
    today = date.today()

    age = today.year - date_of_birth.year

    birthday_has_not_occurred = (
        today.month,
        today.day,
    ) < (
        date_of_birth.month,
        date_of_birth.day,
    )

    if birthday_has_not_occurred:
        age -= 1

    return age


@transaction.atomic
def assess_donor_eligibility(*, donor, answers):
    age = calculate_age(donor.date_of_birth)
    reasons = []

    if age < MINIMUM_AGE:
        reasons.append(
            f"Donor must be at least {MINIMUM_AGE} years old."
        )

    if age > MAXIMUM_AGE:
        reasons.append(
            f"Donor must not be older than {MAXIMUM_AGE} years."
        )

    if donor.weight_kg < MINIMUM_WEIGHT_KG:
        reasons.append(
            (
                "Donor weight must be at least "
                f"{MINIMUM_WEIGHT_KG} kg."
            )
        )

    if not donor.medical_declaration_accepted:
        reasons.append(
            "Medical declaration must be accepted."
        )

    if donor.last_donation_date:
        days_since_last_donation = (
            date.today() - donor.last_donation_date
        ).days

        if days_since_last_donation < 0:
            reasons.append(
                "Last donation date cannot be in the future."
            )
        elif (
            days_since_last_donation
            < MINIMUM_DONATION_INTERVAL_DAYS
        ):
            remaining_days = (
                MINIMUM_DONATION_INTERVAL_DAYS
                - days_since_last_donation
            )

            reasons.append(
                (
                    "Minimum donation interval is not complete. "
                    f"Try again after {remaining_days} day(s)."
                )
            )

    if not answers.get("feeling_well", False):
        reasons.append(
            "Donor must be feeling healthy and well."
        )

    if answers.get("has_fever_or_infection", False):
        reasons.append(
            "Current fever or infection requires medical review."
        )

    if answers.get("taking_antibiotics", False):
        reasons.append(
            "Current antibiotic use requires medical review."
        )

    if answers.get("recent_surgery", False):
        reasons.append(
            "Recent surgery requires medical review."
        )

    if answers.get(
        "pregnant_or_breastfeeding",
        False,
    ):
        reasons.append(
            (
                "Pregnancy or breastfeeding requires "
                "medical review."
            )
        )

    if answers.get(
        "recent_tattoo_or_piercing",
        False,
    ):
        reasons.append(
            (
                "Recent tattoo or piercing requires "
                "medical review."
            )
        )

    assessment = DonorEligibilityAssessment.objects.create(
        donor=donor,
        is_eligible=not reasons,
        age_at_assessment=age,
        weight_at_assessment=donor.weight_kg,
        reasons=reasons,
        answers=answers,
    )

    return assessment