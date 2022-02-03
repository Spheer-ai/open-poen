from datetime import datetime, timedelta
from flask import redirect, url_for
from sqlalchemy.exc import IntegrityError
import os

from app import app, db
from app.models import DebitCard, Payment, BNGAccount
from app.util import formatted_flash
from app.bng import api

import jwt
from flask_login import current_user
from requests import ConnectionError
import collections
import re
from tempfile import TemporaryDirectory
import zipfile
import json
from dateutil.parser import parse
import pytz


def process_bng_callback(request):
    if not current_user.admin or not current_user.is_authenticated:
        formatted_flash("Je hebt niet voldoende rechten om een koppeling met BNG bank aan te maken.", color="red")
        return

    try:
        access_code = request.args.get("code")
        if not access_code: raise TypeError("Toegangscode ontbreekt in callback.")
        token_info = jwt.decode(
            request.args.get("state"),
            app.config["SECRET_KEY"],
            algorithms="HS256"
        )
    except TypeError as e:
        app.logger.error(repr(e))
        formatted_flash(("Er ging iets mis terwijl je toegang verleende aan BNG bank. De beheerder van Open Poen "
                         "is op de hoogte gesteld. Probeer het later nog eens, of neem contact op met de beheerder."),
                        color="red")
        return
    except jwt.ExpiredSignatureError as e:
        app.logger.error(repr(e))
        formatted_flash("Je aanvraag om te koppelen met de BNG is verlopen.", color="red")
        return

    try:
        response = api.retrieve_access_token(access_code)
        access_token, expires_in = response["access_token"], response["expires_in"]
    except ConnectionError as e:
        app.logger.error(repr(e))
        formatted_flash(("Er ging iets mis terwijl je toegang verleende aan BNG bank. De beheerder van Open Poen "
                         "is op de hoogte gesteld. Probeer het later nog eens, of neem contact op met de beheerder."),
                        color="red")
        return

    # We're saving this as a naive datetime with the right timezone to avoid having to configure Postgres.
    expires_on = datetime.now(pytz.timezone("Europe/Amsterdam")) + timedelta(seconds=int(expires_in))
    new_bng_account = BNGAccount(
        user_id=token_info["user_id"],
        consent_id=token_info["consent_id"],
        access_token=access_token,
        expires_on=expires_on.replace(tzinfo=None),
        iban=token_info["iban"]
    )
    db.session.add(new_bng_account)
    db.session.commit()
    formatted_flash("De BNG-koppeling is aangemaakt. Betalingen worden nu op de achtergrond opgehaald.", color="green")

    try:
        get_bng_payments()
        app.logger.info("Succesfully retrieved payments from BNG.")
    except (NotImplementedError, ValueError, IntegrityError, ConnectionError) as e:
        app.logger.error(repr(e))
        formatted_flash(("Het opslaan van de betalingen is mislukt. De beheerder van Open Poen is op de hoogte "
                         "gesteld."), color="red")
        return

    return redirect(url_for("index"))


def get_days_until(date):
    # TODO: Handle timezones gracefully.
    time_left = date - datetime.now()
    days_left = time_left.days
    if days_left < 0:
        days_left = 0
    if days_left < 4:
        color = "red"
    elif days_left < 11:
        color = "orange"
    else:
        color = "green"
    return days_left, color


def get_bng_info(linked_bng_accounts):
    if len(linked_bng_accounts) > 1:
        raise NotImplementedError("Open Poen now only supports a single coupling with a BNG account.")

    date_last_sync_message, date_last_sync_color = "Er heeft nog geen synchronisatie plaatsgevonden.", "grey"

    if len(linked_bng_accounts) == 0:
        return {}

    if len(linked_bng_accounts) == 1:
        bng_account = linked_bng_accounts[0]
        created_color, created = "green", "aangemaakt"
        if bng_account.last_import_on is not None:
            date_last_sync = bng_account.last_import_on.strftime("%d-%m-%Y, %H:%M")
            date_last_sync_message = f"Laatst gesynchroniseerd op {date_last_sync}."
            diff = datetime.now(pytz.timezone("Europe/Amsterdam")).replace(tzinfo=None) - bng_account.last_import_on
            diff_in_hours = diff.seconds / 60 / 60
            if diff_in_hours < 3:
                date_last_sync_color = "green"
            elif diff_in_hours < 8:
                date_last_sync_color = "orange"
            else:
                date_last_sync_color = "red"
        try:
            bng_info = api.retrieve_consent_details(
                bng_account.consent_id,
                bng_account.access_token
            )
        except ConnectionError as e:
            app.logger.error(repr(e))
            formatted_flash(("Er is een BNG-koppeling, maar de status kon niet worden opgehaald. De beheerder van "
                            "Open Poen is op de hoogte gebracht."), color="red")
            status, status_color = "red", "offline"
            days_left, days_left_color = get_days_until(bng_account.expires_on)
        else:
            status = "online" if bng_info["consentStatus"] == "valid" else "offline"
            status_color = "green" if status == "online" else "red"
            days_left, days_left_color = get_days_until(
                datetime.strptime(bng_info["validUntil"], "%Y-%m-%d")
            )

    return {
        "created": {
            "color": created_color,
            "message": f"Koppeling is {created}."
        },
        "status": {
            "color": status_color,
            "message": f"Koppeling is {status}."
        },
        "days_left": {
            "color": days_left_color,
            "message": f"Nog {days_left} dagen geldig."
        },
        "sync": {
            "color": date_last_sync_color,
            "message": date_last_sync_message
        }
    }


def flatten(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def parse_and_save_bng_payments(payments):
    pattern = re.compile(r'(?<!^)(?=[A-Z])')
    new_payments = []

    for payment in payments:
        # Flatten the nested dictionary. Otherwise we won't be able to save it in the database.
        payment = flatten(payment)
        # Convert from camel case to snake case to match the column names in the database.
        payment = {pattern.sub("_", k).lower(): v for (k, v) in payment.items()}
        # These two fields need to be cast. The other fields are strings and should remain so.
        payment["booking_date"] = parse(payment["booking_date"])
        payment["transaction_amount"] = float(payment["transaction_amount"])
        if payment["transaction_amount"] > 0:
            route = "inkomsten"
        else:
            route = "uitgaven"
        # Get the card number, if one was used. This is used to identify what payments where done for
        # what project later on. These numbers always start with 6731924.
        try:
            card_number = re.search("6731924\d*", payment["remittance_information_unstructured"]).group(0)
        except AttributeError:
            card_number = None
        # To simplify things, we always save empty strings as None (NULL).
        payment = {k: (v if v != "" else None) for (k, v) in payment.items()}
        # If we don't do this, payments are registered twice. First time they become accessible through
        # the API without these fields. Then with them. Their transactionId changes when they are updated
        # in the API, so there is no obvious cleaner way to do this.
        if payment["entry_reference"] is None and payment["remittance_information_structured"] is None:
            continue
        new_payments.append(Payment(
            **payment,
            route=route,
            created=datetime.now(),
            card_number=card_number,
            type="BNG"
        ))

    # This is done to ensure we don't save the same transaction twice.
    existing_ids = set([x.transaction_id for x in Payment.query.all()])
    new_payments = [x for x in new_payments if x.transaction_id not in existing_ids]

    # Because we need to save new card numbers before new payments. This has to do
    # with the fact that card_number is a foreign key in the payment table.
    existing_card_numbers = [x.card_number for x in DebitCard.query.all()]
    new_card_numbers = set([x.card_number for x in new_payments
                            if x.card_number not in existing_card_numbers and x.card_number is not None])

    try:
        db.session.bulk_save_objects([DebitCard(card_number=x) for x in new_card_numbers])
        db.session.commit()
    except (ValueError, IntegrityError):
        db.session.rollback()
        raise

    try:
        db.session.bulk_save_objects(new_payments)
        db.session.commit()
    except (ValueError, IntegrityError):
        db.session.rollback()
        raise


def get_bng_payments():
    bng_account = BNGAccount.query.all()
    if len(bng_account) > 1:
        raise NotImplementedError("Op dit moment ondersteunen we slechts één BNG-koppeling.")
    if len(bng_account) == 0:
        return
    bng_account = bng_account[0]

    account_info = api.read_account_information(
        bng_account.consent_id,
        bng_account.access_token
    )
    if len(account_info["accounts"]) > 1:
        raise NotImplementedError("Op dit moment ondersteunen we slechts één consent per BNG-koppeling.")
    elif len(account_info["accounts"]) == 0:
        raise TypeError("Het zou niet mogelijk moeten zijn om wel een account te hebben, maar geen consent.")

    date_from = datetime.today() - timedelta(days=365)
    date_to = datetime.today() - timedelta(days=1)

    # TODO: Make this part asynchronous?
    # TODO: What to do with booking status? Are we interested in pending?
    # TODO: What about balance?

    transaction_list = api.read_transaction_list(
        bng_account.consent_id,
        bng_account.access_token,
        account_info["accounts"][0]["resourceId"],
        date_from.strftime("%Y-%m-%d"),
        date_to.strftime("%Y-%m-%d")
    )

    with TemporaryDirectory() as d:
        with open(os.path.join(d, "transaction_list.zip"), "wb") as f:
            f.write(transaction_list)
        with zipfile.ZipFile(os.path.join(d, "transaction_list.zip")) as z:
            z.extractall(d)
        payment_json_files = [x for x in os.listdir(d) if x.endswith(".json")]
        if len(payment_json_files) != 1:
            raise TypeError("The downloaded transaction zip does not contain a json file.")
        with open(os.path.join(d, payment_json_files[0])) as f:
            payments = json.load(f)
            payments = payments["transactions"]["booked"]

    parse_and_save_bng_payments(payments)

    # We save it as a naive datetime object, but in the right timezone, to avoid having to use timezones
    # in Postgres.
    bng_account.last_import_on = datetime.now(pytz.timezone("Europe/Amsterdam")).replace(tzinfo=None)
    db.session.add(bng_account)
    db.session.commit()
