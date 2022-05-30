from app.models import Project, Funder, Payment, DebitCard, Subproject
from datetime import datetime
from datetime import timedelta
from app import app, db

PROJECT_NAME = "Buurtborrel Oranjebuurt"
FIRST_FUNDER_NAME = "Gemeente Amsterdam"
SECOND_FUNDER_NAME = "Gemeente Groningen"
LAST_DEBIT_CARD = "6731924673192111116"


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
hornbach = {
    "creditor_name": "Hornbach N.V.",
    "creditor_account": "NL68KNAB0448856789",
    **bank_fields,
}


def populate_db_with_test_data():
    project = {
        "name": PROJECT_NAME,
        "description": "Buurtborrel / -BBQ voor de Oranjebuurt in Groningen.",
        "purpose": "Creëren van saamhorigheid/gemeenschapsgevoel in de Oranjebuurt",
        "target_audience": "40+ en jonger dan 18.",
        "owner": "Jaap Koen Bijma",
        "owner_email": "jaapkoenbijma@amsterdam.nl",
        "legal_entity": "Stichting",
        "address_applicant": "De Dam 14, 9889 ST",
        "registration_kvk": "1334998890",
        "project_location": "Groningen",
        "budget": 10000,
    }
    project = Project(**project)

    funders = [
        {
            "name": FIRST_FUNDER_NAME,
            "url": "http://amsterdam.nl",
            "subsidy": "Buurtbudget",
            "subsidy_number": "XYZ-12345678",
            "budget": 2500,
        },
        {
            "name": SECOND_FUNDER_NAME,
            "url": "http://gemeente.groningen.nl",
            "subsidy": "Verzamelpotje",
            "subsidy_number": "ABC-87654321",
            "budget": 2500,
        },
        {
            "name": "Het Koningshuis",
            "url": "http://www.koninklijkhuis.nl/",
            "subsidy": "Het Oranjefonds",
            "subsidy_number": "WIM-LEX-1756",
            "budget": 5000,
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
        {"card_number": LAST_DEBIT_CARD},
    ]
    debit_cards = [DebitCard(**x) for x in debit_cards]
    project.debit_cards.extend(debit_cards)

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


def add_subprojects():
    project = Project.query.filter(Project.name == PROJECT_NAME).first()

    subprojects = [
        {
            "name": "Eten",
            "description": "Inkopen van eten.",
            "purpose": "Ervoor zorgen dat er voldoende te eten is voor iedereen, inclusief veganistische en vegetarische opties.",
            "target_audience": "Alle bezoekers van de BBQ/borrel.",
            "budget": 1000,
        },
        {
            "name": "Drinken",
            "description": "Inkopen van drinken.",
            "purpose": "Niemand mag dorst krijgen. Alcoholische dranken niet inbegrepen.",
            "target_audience": "Alle bezoekers van de BBQ/borrel.",
            "budget": 1000,
        },
    ]
    subprojects = [Subproject(**x) for x in subprojects]
    first_funder = Funder.query.filter(Funder.name == FIRST_FUNDER_NAME).first()
    first_funder.subprojects.extend(subprojects)
    second_funder = Funder.query.filter(Funder.name == SECOND_FUNDER_NAME).first()
    second_funder.subprojects.extend(subprojects)
    project.subprojects.extend(subprojects)

    first_subproject_payments = [
        {
            **hema,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -25,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            **hema,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -50,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            **hornbach,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -100,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            **hornbach,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -100,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            "booking_date": datetime.now() - timedelta(13),
            "transaction_amount": 1000,
            "route": "inkomsten",
            "type": "BNG",
        },
    ]
    first_subproject_payments = [Payment(**x) for x in first_subproject_payments]
    subprojects[0].payments.extend(first_subproject_payments)
    debit_card = DebitCard.query.filter(DebitCard.card_number == LAST_DEBIT_CARD).one()
    debit_card.payments.extend(first_subproject_payments)
    project.payments.extend(first_subproject_payments)

    second_subproject_payments = [
        {
            **hema,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -200,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            **hema,
            "booking_date": datetime.now() - timedelta(12),
            "transaction_amount": -200,
            "route": "uitgaven",
            "type": "BNG",
        },
        {
            "booking_date": datetime.now() - timedelta(13),
            "transaction_amount": 1000,
            "route": "inkomsten",
            "type": "BNG",
        },
    ]
    second_subproject_payments = [Payment(**x) for x in second_subproject_payments]
    subprojects[1].payments.extend(second_subproject_payments)
    debit_card.payments.extend(second_subproject_payments)
    project.payments.extend(second_subproject_payments)

    try:
        db.session.add(project)
        db.session.add(first_funder)
        db.session.add(second_funder)
        db.session.add(debit_card)
        db.session.commit()
        app.logger.info("Succesfully added subprojects to the test project.")
    except Exception as e:
        app.logger.error(f"Failed to add subprojects: {repr(e)}")
        db.session.rollback()


def delete_test_data():
    project = Project.query.filter(Project.name == PROJECT_NAME).first()
    if project is None:
        return

    Funder.query.filter(Funder.project_id == project.id).delete()
    Payment.query.filter(Payment.project_id == project.id).delete()
    card_numbers = [
        x.card_number
        for x in DebitCard.query.filter(DebitCard.project_id == project.id).all()
    ]
    Payment.query.filter(Payment.card_number.in_(card_numbers)).delete(
        synchronize_session="fetch"
    )
    DebitCard.query.filter(DebitCard.project_id == project.id).delete()
    db.session.delete(project)

    try:
        db.session.commit()
        app.logger.info("Succesfully deleted the test project.")
    except Exception as e:
        app.logger.error(f"Failed to delete the test project: {repr(e)}")
        db.session.rollback()
