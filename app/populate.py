from app.models import Project, Funder, Payment, DebitCard
from datetime import datetime
from datetime import timedelta
from app import app, db


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

    debit_cards = [
        {"card_number": "6731924673192111111"},
        {"card_number": "6731924673192111112"},
        {"card_number": "6731924673192111113"},
        {"card_number": "6731924673192111114"},
        {"card_number": "6731924673192111115"},
        {"card_number": "6731924673192111116"},
    ]
    debit_cards = [DebitCard(**x) for x in debit_cards]
    project.debit_cards.extend(debit_cards)

    bank_fields = {
        "remittance_information_unstructured": "Beschrijving van de bank.",
        "remittance_information_structured": "Beschrijving van de bank.",
    }
    macro = {
        "creditor_name": "Macro B.V.",
        "creditor_account": "NL32INGB0008529777",
        **bank_fields,
    }
    qilo = {
        "creditor_name": "Qilo B.V.",
        "creditor_account": "NL69INGB0123456789",
        **bank_fields,
    }
    hema = {
        "creditor_name": "HEMA N.V.",
        "creditor_account": "NL68KNAB0123456789",
        **bank_fields,
    }

    manual_payments = [
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
            **bank_fields,
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
            **bank_fields,
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
    manual_payments = [Payment(**x) for x in manual_payments]
    project.payments.extend(manual_payments)

    first_debit_card_payments = [
        {
            **hema,
            "booking_date": datetime.now() - timedelta(7),
            "transaction_amount": -15,
            "route": "uitgaven",
            "type": "BNG",
            "short_user_description": "Bandenplakspullen.",
            "long_user_description": "Voor de workshop banden plakken.",
        },
        {
            **hema,
            "booking_date": datetime.now() - timedelta(8),
            "transaction_amount": -5,
            "route": "uitgaven",
            "type": "BNG",
            "short_user_description": "Taart voor de lunch.",
            "long_user_description": "Geen nadere toelichting.",
        },
        {
            "booking_date": datetime.now() - timedelta(9),
            "transaction_amount": 30,
            "route": "inkomsten",
            "type": "BNG",
            "short_user_description": "Storting budget.",
        },
    ]
    first_debit_card_payments = [Payment(**x) for x in first_debit_card_payments]
    debit_cards[0].payments.extend(first_debit_card_payments)

    second_debit_card_payments = [
        {
            **hema,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -5,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            **hema,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -5,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            "booking_date": datetime.now() - timedelta(13),
            "transaction_amount": 10,
            "route": "inkomsten",
            "type": "MANUAL_TOPUP",
        },
    ]
    second_debit_card_payments = [Payment(**x) for x in second_debit_card_payments]
    debit_cards[1].payments.extend(second_debit_card_payments)

    try:
        db.session.add(project)
        db.session.commit()
        app.logger.info("Succesfully populated the database.")
    except Exception as e:
        app.logger.error(f"Failed to populate database: {repr(e)}")
        db.session.rollback()
