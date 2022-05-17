import enum
import locale
from datetime import datetime, timedelta
from typing import Dict

from babel.numbers import format_percent
from flask import flash
from flask_login import current_user

from app import app, db
from app.models import Project, Subproject, Funder, Payment


def formatted_flash(text, color):
    return flash(f'<span class="text-default-{color}">' + text + "</span>")


def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0

    if magnitude > 0:
        return "%s%s" % (locale.format("%.1f", num), ["", "K", "M"][magnitude])
    else:
        return locale.format("%.1f", round(num))


def format_currency(num, currency_symbol="€ "):
    return "%s%s" % (
        currency_symbol,
        locale.format("%d", round(num), grouping=True, monetary=True),
    )


def calculate_amounts(model, id, payments):
    instance = model.query.get(id)

    awarded, expenses, insourcing = 0, 0, 0
    awarded += sum([x.transaction_amount for x in payments if x.route == "inkomsten"])
    # Make spent a positive number to make the output of this function consistent with
    # previous versions.
    expenses += -sum([x.transaction_amount for x in payments if x.route == "uitgaven"])
    insourcing += -sum(
        [x.transaction_amount for x in payments if x.route == "inbesteding"]
    )

    if not hasattr(
        instance, "budget"
    ):  # Hack to make this function work with debit cards.
        instance.budget = None

    if instance.budget:
        spent = expenses + insourcing
    else:
        spent = expenses

    amounts = {
        "id": id,
        "awarded": awarded,
        "awarded_str": format_currency(awarded),
        "spent": spent,
    }

    # Calculate percentage spent
    denominator = amounts["awarded"]
    if instance.budget:
        denominator = instance.budget

    if denominator == 0:
        amounts["percentage_spent_str"] = format_percent(0)
        amounts["percentage"] = 0
    else:
        amounts["percentage_spent_str"] = format_percent(amounts["spent"] / denominator)
        amounts["percentage"] = round(amounts["spent"] / denominator * 100)

    amounts["spent_str"] = format_currency(amounts["spent"])

    amounts["left_str"] = format_currency(round(amounts["awarded"] - amounts["spent"]))
    if instance.budget:
        amounts["left_str"] = format_currency(round(instance.budget - amounts["spent"]))

    return amounts


def form_in_request(form, request):
    if not request.form:
        return False

    if next(iter(request.form)).startswith(form._prefix):
        return True
    else:
        return False


def flash_form_errors(form, request):
    # Don't print the errors if the request doesn't contain values for
    # this form
    if not request.form:
        return
    if not form_in_request(form, request):
        return

    for f in form:
        for error in f.errors:
            flash('<span class="text-default-red">%s: %s</span>' % (f.label, error))


def validate_on_submit(form, request):
    if form_in_request(form, request):
        return form.validate_on_submit()
    else:
        return False


def get_export_timestamp():
    return (
        datetime.now(app.config["TZ"])
        .isoformat()[:19]
        .replace("-", "_")
        .replace("T", "-")
        .replace(":", "_")
    )


class Clearance(enum.IntEnum):
    ANONYMOUS = 1
    SUBPROJECT_OWNER = 2
    PROJECT_OWNER = 3
    FINANCIAL = 4
    ADMIN = 5


def get_permissions(clearance: Clearance) -> Dict[str, bool]:
    # TODO: construct this directly from Clearance.
    permissions = {
        "ANONYMOUS": 1,
        "SUBPROJECT_OWNER": 2,
        "PROJECT_OWNER": 3,
        "FINANCIAL": 4,
        "ADMIN": 5,
    }
    return {k: v <= clearance.value for k, v in permissions.items()}


def get_index_clearance() -> Clearance:
    if not current_user.is_authenticated:
        return Clearance.ANONYMOUS
    elif current_user.admin:
        return Clearance.ADMIN
    elif current_user.financial:
        return Clearance.FINANCIAL
    else:
        # Default to anonymous, because that's the lowest level of clearance.
        return Clearance.ANONYMOUS


def get_project_clearance(project: Project) -> Clearance:
    if not current_user.is_authenticated:
        return Clearance.ANONYMOUS
    elif current_user.admin:
        return Clearance.ADMIN
    elif current_user.financial:
        return Clearance.FINANCIAL
    elif project.has_user(current_user.id):
        return Clearance.PROJECT_OWNER
    elif project.contains_subprojects and any(
        [subproject.has_user(current_user.id) for subproject in project.subprojects]
    ):
        return Clearance.SUBPROJECT_OWNER
    else:
        # Default to anonymous, because that's the lowest level of clearance.
        return Clearance.ANONYMOUS


def get_subproject_clearance(subproject: Subproject) -> Clearance:
    if not current_user.is_authenticated:
        return Clearance.ANONYMOUS
    elif current_user.admin:
        return Clearance.ADMIN
    elif current_user.financial:
        return Clearance.FINANCIAL
    elif subproject.project.has_user(current_user.id):
        return Clearance.PROJECT_OWNER
    elif subproject.has_user(current_user.id):
        return Clearance.SUBPROJECT_OWNER
    else:
        # Default to anonymous, because that's the lowest level of clearance.
        return Clearance.ANONYMOUS


def populate_db_with_test_data():
    project = {
        "name": "Buurtborrel Oranjebuurt",
        "description": "Buurtborrel / -BBQ voor de Oranjebuurt in Groningen.",
        "purpose": "Creëren van saamhorigheid/gemeenschapsgevoel in de Oranjebuurt",
        "target_audience": "40+ en jonger dan 18.",
        "contains_subprojects": True,
        "owner": "Jaap Koen Bijma",
        "owner_email": "jaapkoenbijma@amsterdam.nl",
        "legal_entity": "Stichting",
        "address_applicant": "De Dam 14, 9889 ST",
        "registration_kvk": "1334998890",
        "project_location": "Amsterdam",
        "budget": 300,
    }
    project = Project(**project)

    subprojects = [
        {
            "name": "Eten",
            "description": "Vlees en vegaproducten voor de BBQ.",
            "purpose": "Ervoor zorgen dat niemand honger krijgt.",
            "target_audience": "Alle bezoekers.",
            "budget": 150,
        },
        {
            "name": "Drinken",
            "description": "Zowel alcoholisch, als niet alcoholisch.",
            "purpose": "Ervoor zorgen dat niemand dorst krijgt.",
            "target_audience": "Alle bezoekers.",
            "budget": 50,
        },
        {
            "name": "Muziek",
            "description": "Voor het inkopen van live muziek.",
            "purpose": "Ervoor zorgen dat er gedanst kan worden.",
            "target_audience": "Alle bezoekers.",
            "budget": 100,
        },
    ]
    subprojects = [Subproject(**x) for x in subprojects]
    project.subprojects.extend(subprojects)

    funders = [
        {
            "name": "Gemeente Amsterdam",
            "url": "http://amsterdam.nl",
            "subsidy": "Buurtbudget",
            "subsidy_number": "XYZ-12345678",
            "budget": 200,
        },
        {
            "name": "Gemeente Groningen",
            "url": "http://gemeente.groningen.nl",
            "subsidy": "Verzamelpotje",
            "subsidy_number": "ABC-87654321",
            "budget": 100,
        },
    ]
    funders = [Funder(**x) for x in funders]
    project.funders.extend(funders)

    macro = {
        "creditor_name": "Macro B.V.",
        "creditor_account": "NL32INGB0008529777",
        "remittance_information_unstructured": "Beschrijving van de bank.",
        "remittance_information_structured": "Beschrijving van de bank.",
    }
    qilo = {
        "creditor_name": "Qilo B.V.",
        "creditor_account": "NL69INGB0123456789",
        "remittance_information_unstructured": "Beschrijving van de bank.",
        "remittance_information_structured": "Beschrijving van de bank.",
    }

    payments = [
        {
            **macro,
            "booking_date": datetime.now(),
            "transaction_amount": -100,
            "debtor_name": "M.M.T. de Wijk",
            "debtor_account": "NL02ABNA0123456789",
            "route": "uitgaven",
            "card_number": None,
            "type": "MANUAL_PAYMENT",
            "short_user_description": "Vlees voor de BBQ.",
            "long_user_description": "Voor de BBQ als onderdeel van de borrel.",
        },
        {
            **macro,
            "booking_date": datetime.now(),
            "transaction_amount": -50,
            "debtor_name": "M.M.T. de Wijk",
            "debtor_account": "NL02ABNA0123456789",
            "route": "uitgaven",
            "card_number": None,
            "type": "MANUAL_PAYMENT",
            "short_user_description": "Vleesvervangers voor de BBQ.",
            "long_user_description": "Voor de BBQ als onderdeel van de borrel.",
        },
        {
            **macro,
            "booking_date": datetime.now(),
            "transaction_amount": -50,
            "debtor_name": "M.M.T. de Wijk",
            "debtor_account": "NL02ABNA0123456789",
            "route": "uitgaven",
            "card_number": None,
            "type": "MANUAL_PAYMENT",
            "short_user_description": "Drinken voor de BBQ en de borrel.",
            "long_user_description": "Water, bier en ranja.",
        },
        {
            **qilo,
            "booking_date": datetime.now() - timedelta(1),
            "transaction_amount": -10,
            "debtor_name": "M.M.T. de Wijk",
            "debtor_account": "NL02ABNA0123456789",
            "route": "uitgaven",
            "card_number": None,
            "type": "MANUAL_PAYMENT",
            "short_user_description": "Twee kilo's bananen voor de fruitdesserts.",
            "long_user_description": "Aan het eind van de borrel maakt Greetje Westers fruitdesserts voor iedereen.",
        },
        {
            **qilo,
            "booking_date": datetime.now() - timedelta(2),
            "transaction_amount": -10,
            "debtor_name": "M.M.T. de Wijk",
            "debtor_account": "NL02ABNA0123456789",
            "route": "uitgaven",
            "card_number": None,
            "type": "MANUAL_PAYMENT",
            "short_user_description": "Een kilo aarbeien.",
            "long_user_description": "Tevens voor de fruitdesserts.",
        },
        {
            "creditor_name": "M.M.T. de Wijk",
            "creditor_account": "NL02ABNA0123456789",
            "remittance_information_unstructured": "Beschrijving van de bank.",
            "remittance_information_structured": "Beschrijving van de bank.",
            "booking_date": datetime.now(),
            "transaction_amount": 5,
            "debtor_name": "Qilo B.V.",
            "debtor_account": "NL69INGB0123456789",
            "route": "uitgaven",
            "card_number": None,
            "type": "MANUAL_PAYMENT",
            "short_user_description": "Correctie.",
            "long_user_description": "Per ongeluk te veel betaald voor de aarbeien. Geld teruggekregen van Qilo.",
        },
        {
            "creditor_name": "M.M.T. de Wijk",
            "creditor_account": "NL02ABNA0123456789",
            "remittance_information_unstructured": "Beschrijving van de bank.",
            "remittance_information_structured": "Beschrijving van de bank.",
            "booking_date": datetime.now() - timedelta(14),
            "transaction_amount": 200,
            "debtor_name": "Gemeente Amsterdam",
            "debtor_account": "NL66BNGH0123456789",
            "route": "inkomsten",
            "card_number": None,
            "type": "MANUAL_PAYMENT",
            "short_user_description": "Storting budget van Gemeente Amsterdam.",
            "long_user_description": "Storting van het volledige budget: 200 euro.",
        },
    ]
    payments = [Payment(**x) for x in payments]
    project.payments.extend(payments)

    try:
        db.session.add(project)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Failed to populate database: {e}")
        db.session.rollback()

    app.logger.info("Succesfully populated the database.")
