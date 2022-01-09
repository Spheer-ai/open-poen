from datetime import datetime, timedelta
from flask import flash, redirect, url_for, request
from flask.templating import render_template
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import os

from wtforms.validators import ValidationError

from app import app, db
from app.forms import CategoryForm, NewPaymentForm, PaymentForm, EditAttachmentForm
from app.models import Category, DebitCard, Funder, Payment, File, Project, User, Subproject, BNGAccount
from app.util import flash_form_errors, form_in_request, formatted_flash
from app import util
from app import bng as bng

import jwt
from flask_login import current_user
from time import time
from requests import ConnectionError
import collections
import re
from tempfile import TemporaryDirectory
import zipfile
import json
from dateutil.parser import parse

fields_to_exclude = ["SubmitField", "CSRFTokenField"]


def return_redirect(project_id, subproject_id):
    # Redirect back to clear form data
    if subproject_id:
        return redirect(
            url_for(
                'subproject',
                project_id=project_id,
                subproject_id=subproject_id
            )
        )

    return redirect(
        url_for(
            'project',
            project_id=project_id
        )
    )


# Process filled in category form
def process_category_form(request):
    category_form = CategoryForm(prefix="category_form")

    # Check whether the category form is for a project or subproject
    project_id = category_form.project_id.data
    subproject_id = 0
    if category_form.subproject_id.data:
        subproject_id = category_form.subproject_id.data

    # Remove category
    if category_form.remove.data:
        Category.query.filter_by(id=category_form.id.data).delete()
        db.session.commit()
        flash(
            '<span class="text-default-green">Categorie "%s" is verwijderd</span>' % (
                category_form.name.data
            )
        )
        return return_redirect(project_id, subproject_id)

    # Update or save category
    if category_form.validate_on_submit():
        category = Category.query.filter_by(id=category_form.id.data)
        if len(category.all()):
            category.update({'name': category_form.name.data})
            db.session.commit()
            flash(
                '<span class="text-default-green">Categorie is bijgewerkt</span>'
            )
        else:
            try:
                if subproject_id:
                    category = Category(
                        name=category_form.name.data,
                        subproject_id=subproject_id
                    )
                else:
                    category = Category(
                        name=category_form.name.data,
                        project_id=project_id
                    )
                db.session.add(category)
                db.session.commit()
                flash(
                    '<span class="text-default-green">Categorie '
                    f'{category_form.name.data} is toegevoegd</span>'
                )
            except IntegrityError as e:
                db.session().rollback()
                app.logger.error(repr(e))
                flash(
                    '<span class="text-default-red">Categorie toevoegen mislukt: naam '
                    f'"{category_form.name.data}" bestaat al, kies een '
                    'andere naam<span>'
                )

        # Redirect back to clear form data
        return return_redirect(project_id, subproject_id)
    else:
        flash_form_errors(category_form, request)


# Process filled in payment form
def process_payment_form(request, project_or_subproject, project_owner, user_subproject_ids, is_subproject):
    form_keys = list(request.form.keys())
    if len(form_keys) > 0 and form_keys[0].startswith("payment_form_"):
        id_key = [x for x in list(request.form.keys()) if "-id" in x][0]
        id_key = id_key.split("-")[0]
    else:
        return

    payment_form = PaymentForm(prefix=id_key)
    # Somehow we need to repopulate the category_id.choices with the same
    # values as used when the form was generated. Probably to validate
    # if the selected value is valid. We don't know the subproject in the
    # case of an edited payment on a project page which contains subprojects,
    # so we need to retrieve this before running validate_on_submit
    temppayment = Payment.query.filter_by(
        id=payment_form.id.data
    ).first()
    if temppayment:
        if temppayment.subproject:
            payment_form.category_id.choices = temppayment.subproject.make_category_select_options()
        else:
            #     # If a payment is not manually assigned to a subproject, we have to go by the debit
            #     # card that is associated with the payment, unless it has been manually added. This,
            #     # still have to implement. # TODO
            payment_form.category_id.choices = temppayment.debit_card.project.make_category_select_options()

        if temppayment.debit_card.project.contains_subprojects:
            payment_form.subproject_id.choices = temppayment.debit_card.project.make_subproject_select_options()

        # Make sure the user is allowed to edit this payment
        # (especially needed when a normal users edits a subproject
        # payment on a project page)
        if not project_owner and not temppayment.subproject.id in user_subproject_ids:
            return
        # Make sure the transaction amount can't be changed if the transaction is not manual.
        if temppayment.type != "MANUAL":
            payment_form.transaction_amount.data = temppayment.transaction_amount
    else:
        return

    payment_form.route.choices = [
        ('inkomsten', 'inkomsten'),
        ('inbesteding', 'inbesteding'),
        ('uitgaven', 'uitgaven')
    ]

    # When the user removes a manually added payment, the route selection
    # field will have no value and validate_on_submit will fail, so add a
    # default value
    if payment_form.route.data == 'None':
        payment_form.route.data = 'inkomsten'

    if payment_form.validate_on_submit():
        # Remove payment
        if payment_form.remove.data:
            Payment.query.filter_by(id=payment_form.id.data).delete()
            db.session.commit()
            flash(
                '<span class="text-default-green">Transactie is verwijderd</span>'
            )
        # Get data from the form
        else:
            # TODO: We don't want this hardcoded.
            new_payment_fields = ["short_user_description", "long_user_description", "transaction_amount", "created",
                                  "hidden", "category_id", "subproject_id", "route", "id"]
            new_payment_data = {x.short_name: x.data for x in payment_form if x.short_name in new_payment_fields}
            new_payment_data["category_id"] = None if new_payment_data["category_id"] == "" else new_payment_data["category_id"]
            new_payment_data["subproject_id"] = None if new_payment_data["subproject_id"] == "" else new_payment_data["subproject_id"]

            try:
                # Update if the payment already exists
                payments = Payment.query.filter_by(
                    id=payment_form.id.data
                )

                # In case of a manual payment we update the updated field with
                # the current timestamp
                if payments.first().type == 'MANUAL':
                    new_payment_data['updated'] = datetime.now()

                # In case of non-manual payments we don't allow the modification
                # of the 'created' field, so we need to fill in the form with
                # created timestamp that already exists
                if payments.first().type != 'MANUAL':
                    new_payment_data['created'] = payments.first().created

                if len(payments.all()):
                    payments.update(new_payment_data)
                    db.session.commit()
                    flash(
                        '<span class="text-default-green">Transactie is bijgewerkt</span>'
                    )
            except IntegrityError as e:
                db.session().rollback()
                app.logger.error(repr(e))
                flash(
                    '<span class="text-default-red">Transactie bijwerken mislukt<span>'
                )

        if is_subproject:
            # Redirect back to clear form data
            return redirect(
                url_for(
                    'subproject',
                    project_id=project_or_subproject.project_id,
                    subproject_id=project_or_subproject.id
                )
            )

        # Redirect back to clear form data
        return redirect(
            url_for(
                'project',
                project_id=project_or_subproject.id,
            )
        )
    else:
        return payment_form


# Populate the payment forms which allows the user to edit it
def create_payment_forms(payments):
    payment_forms = {}
    for payment in payments:
        payment_form = PaymentForm(prefix=f'payment_form_{payment.id}', **{
            'short_user_description': payment.short_user_description,
            'long_user_description': payment.long_user_description,
            'created': payment.created,
            'transaction_amount': payment.transaction_amount,
            'id': payment.id,
            'hidden': payment.hidden,
            'category_id': "" if payment.category is None else payment.category.id,
            'subproject_id': "" if payment.subproject is None else payment.subproject.id,
            'route': payment.route
        })

        if payment.type != 'MANUAL':
            del payment_form['created']
            del payment_form['remove']

        if payment.subproject:
            payment_form.category_id.choices = payment.subproject.make_category_select_options()
        else:
            # If a payment is not manually assigned to a subproject, we have to go by the debit
            # card that is associated with the payment, unless it has been manually added. This,
            # still have to implement. # TODO
            payment_form.category_id.choices = payment.debit_card.project.make_category_select_options()

        if payment.debit_card.project.contains_subprojects:
            payment_form.subproject_id.choices = payment.debit_card.project.make_subproject_select_options()

        payment_form.route.choices = [
            ('inkomsten', 'inkomsten'),
            ('inbesteding', 'inbesteding'),
            ('uitgaven', 'uitgaven')
        ]

        payment_forms[payment.id] = payment_form
    return payment_forms


# Save attachment to disk
def save_attachment(f, mediatype, db_object, folder):
    filename = secure_filename(f.filename)
    filename = '%s_%s' % (
        datetime.now(app.config['TZ']).isoformat()[:19], filename
    )
    filepath = os.path.join(
        os.path.abspath(
            os.path.join(
                app.instance_path, '../%s/%s' % (
                    app.config['UPLOAD_FOLDER'],
                    folder
                )
            )
        ),
        filename
    )
    f.save(filepath)
    new_file = File(filename=filename, mimetype=f.headers[1][1], mediatype=mediatype)
    db.session.add(new_file)
    db.session.commit()

    # Link attachment to payment in the database
    # If the db object is a User, then save as FK and store the id
    if isinstance(db_object, User):
        db_object.image = new_file.id
        db.session.commit()
    # Elif this is a Payment, then save as many-to-many and we need to append
    elif isinstance(db_object, Payment):
        db_object.attachments.append(new_file)
        db.session.commit()


# Process filled in transaction attachment form
def process_transaction_attachment_form(request, transaction_attachment_form, project_owner, user_subproject_ids,
                                        project_id=0, subproject_id=0):
    if form_in_request(transaction_attachment_form, request):
        if transaction_attachment_form.validate_on_submit():
            payment = Payment.query.get(
                transaction_attachment_form.payment_id.data
            )
            # Make sure the user is allowed to edit this payment
            # (especially needed when a normal users edits a subproject
            # payment on a project page)
            if not project_owner and not payment.subproject.id in user_subproject_ids:
                return

            save_attachment(transaction_attachment_form.data_file.data,
                            transaction_attachment_form.mediatype.data, payment, 'transaction-attachment')

            # Redirect back to clear form data
            if subproject_id:
                # Redirect back to clear form data
                return redirect(
                    url_for(
                        'subproject',
                        project_id=project_id,
                        subproject_id=subproject_id
                    )
                )

            return redirect(
                url_for(
                    'project',
                    project_id=project_id,
                )
            )
        else:
            flash_form_errors(transaction_attachment_form, request)


# Populate the edit attachment forms which allows the user to edit it
def create_edit_attachment_forms(attachments):
    edit_attachment_forms = {}
    for attachment in attachments:
        edit_attachment_form = EditAttachmentForm(prefix='edit_attachment_form', **{
            'id': attachment.id,
            'mediatype': attachment.mediatype
        })

        edit_attachment_forms[attachment.id] = edit_attachment_form

    return edit_attachment_forms


def process_edit_attachment_form(request, edit_attachment_form, project_id=0, subproject_id=0):
    edit_attachment_form = EditAttachmentForm(prefix="edit_attachment_form")

    if edit_attachment_form.validate_on_submit():
        # Remove attachment
        if edit_attachment_form.remove.data:
            File.query.filter_by(id=edit_attachment_form.id.data).delete()
            db.session.commit()
            flash('<span class="text-default-green">Media is verwijderd</span>')
        else:
            new_data = {}
            for f in edit_attachment_form:
                if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                    new_data[f.short_name] = f.data

            try:
                # Update if the attachment already exists
                attachments = File.query.filter_by(
                    id=edit_attachment_form.id.data
                )

                if len(attachments.all()):
                    attachments.update(new_data)
                    db.session.commit()
                    flash(
                        '<span class="text-default-green">Media is bijgewerkt</span>'
                    )
            except IntegrityError as e:
                db.session().rollback()
                app.logger.error(repr(e))
                flash(
                    '<span class="text-default-red">Media bijwerken mislukt<span>'
                )

        # Redirect back to clear form data
        if subproject_id:
            # Redirect back to clear form data
            return redirect(
                url_for(
                    'subproject',
                    project_id=project_id,
                    subproject_id=subproject_id
                )
            )

        return redirect(
            url_for(
                'project',
                project_id=project_id,
            )
        )
    else:
        flash_form_errors(edit_attachment_form, request)


def process_new_payment_form(form, project, subproject):
    if not util.validate_on_submit(form, request):
        return None

    if project:
        redirect_url = url_for("project", project_id=project.id)
    elif subproject:
        redirect_url = url_for(
            "subproject",
            project_id=subproject.project.id,
            subproject_id=subproject.id
        )
    else:
        raise ValidationError("No project or subproject supplied.")

    new_payment = {}
    for f in form:
        if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
            new_payment[f.short_name] = f.data
    media_type = new_payment.pop("mediatype")
    data_file = new_payment.pop("data_file")

    # This is necessary, because the subproject id is assigned dynamically in the
    # form when it is submitted from the project page.
    if form.subproject:
        new_payment["subproject_id"] = new_payment["subproject"]
        del new_payment["subproject"], new_payment["project_id"]

    value = new_payment["category_id"]
    new_payment["category_id"] = None if value == "" else value

    new_payment = Payment(**new_payment)
    new_payment.amount_currency = 'EUR'
    new_payment.type = 'MANUAL'
    new_payment.updated = datetime.now()

    # Payments are not allowed to have both a project and a subproject id.
    if new_payment.project_id and new_payment.subproject_id:
        raise ValidationError("Project and subproject ID are mutually exclusive.")

    try:
        db.session.add(new_payment)
        db.session.commit()
        formatted_flash("Transactie is toegevoegd", "green")

    except (ValueError, IntegrityError) as e:
        db.session.rollback()
        app.logger.error(repr(e))
        formatted_flash("Transactie toevoegen mislukt.", "red")
        return redirect(redirect_url)
    if data_file is not None:
        save_attachment(
            data_file,
            media_type,
            new_payment,
            'transaction-attachment'
        )
    return redirect(redirect_url)


def generate_new_payment_form(project, subproject):
    if project and subproject:
        raise ValidationError("Cannot create a payment form for a project and a subproject at once.")

    form = NewPaymentForm(prefix="new_payment_form")

    if project:
        form.project_id.data = project.id
        if project.subprojects.first() is not None:
            form.category_id.choices = project.subprojects[0].make_category_select_options()
            form.subproject.choices = [(x.id, x.name) for x in project.subprojects]
            return form
        else:
            form.category_id.choices = project.make_category_select_options()
            del form.subproject
            return form

    if subproject:
        form.subproject_id.data = subproject.id
        del form.subproject
        form.category_id.choices = subproject.make_category_select_options()
        return form


def process_new_project_form(form):
    if form_in_request(form, request):
        # We need to rerender the form if the user wants to add funders, debit cards or subprojects, but hasn't
        # received the rerendered form yet to actually enter those.
        # TODO: Refactor.
        rerender = False
        funders_to_add = form.funders_amount.data - len(form.funders)
        if funders_to_add > 0:
            for x in range(0, funders_to_add):
                form.funders.append_entry()
            rerender = True
        debit_cards_to_add = form.card_numbers_amount.data - len(form.card_numbers)
        if debit_cards_to_add > 0:
            for x in range(0, debit_cards_to_add):
                form.card_numbers.append_entry()
            rerender = True
        subprojects_to_add = form.subprojects_amount.data - len(form.subprojects)
        if subprojects_to_add > 0:
            for x in range(0, subprojects_to_add):
                form.subprojects.append_entry()
            rerender = True
        if rerender:
            del form.funders_amount
            del form.card_numbers_amount
            del form.subprojects_amount
            form.errors["rerender"] = "rerender"
            return

    if not util.validate_on_submit(form, request):
        return

    # TODO: We don't want this hardcoded.
    new_project_fields = ["name", "description", "contains_subprojects", "hidden", "hidden_sponsors", "budget"]
    new_project_data = {x.short_name: x.data for x in form if x.short_name in new_project_fields}
    new_project = Project(**new_project_data)

    # Of all the cards entered, check whether they already exist. (Debit cards are created as payments are parsed.)
    # If they already exist, we just need to assign them to the project that we are creating. If they are already
    # assigned to a project, the user made a mistake. If the card does not exist yet, a payment for that card has
    # never been parsed yet, but that doesn't matter to the user, so we add it in advance.
    card_numbers = [x.card_number.data for x in form.card_numbers]
    already_existing_debit_cards = [x for x in DebitCard.query.all() if x.card_number in card_numbers]
    new_debit_cards = [DebitCard(card_number=x) for x in card_numbers
                       if x not in [i.card_number for i in already_existing_debit_cards]]

    funders = [Funder(name=x.form.name.data, url=x.form.url.data) for x in form.funders]

    # TODO: We don't want this hardcoded.
    new_subproject_fields = ["name", "description", "hidden", "budget"]
    new_subproject_data = [{x.short_name: x.data for x in i
                           if x.short_name in new_subproject_fields} for i in form.subprojects]
    subprojects = [Subproject(**x) for x in new_subproject_data]
    if not len(subprojects) == len(set([x.name for x in subprojects])):
        formatted_flash(("Minstens twee initiatieven hebben dezelfde naam. Geef elk initiatief "
                         "een unieke naam om een project aan te maken."),
                        color="red")
        return

    new_project.debit_cards = already_existing_debit_cards + new_debit_cards
    new_project.funders = funders
    new_project.subprojects = subprojects

    try:
        db.session.add(new_project)
        db.session.commit()
        formatted_flash(f"Project {new_project.name} is toegevoegd.", color="green")
        return redirect(url_for("index"))
    except (ValueError, IntegrityError) as e:
        app.logger.error(repr(e))
        db.session().rollback()
        # This should, in practise, be the only case possible that results in the aforementioned exceptions.
        formatted_flash(f"Het project is niet toegevoegd. Er bestaat al een project met de naam {new_project.name}.",
                        color="red")


def process_bng_link_form(form):
    if not current_user.is_authenticated or not current_user.admin:
        return None

    if form.remove.data:
        bng_account = BNGAccount.query.filter_by(user_id=current_user.id).all()
        if len(bng_account) > 1:
            raise NotImplementedError("A user should not be able to have more than one BNG account.")
        if len(bng_account) == 0:
            formatted_flash(("De BNG-koppeling is niet verwijderd. Alleen degene die de koppeling heeft aangemaakt, "
                             "mag deze verwijderen."), color="red")
            return
        bng_account = bng_account[0]

        # TODO: This returns a 401 now for the Sandbox, but I don't see how there is
        # anything wrong with my request.
        # bng.delete_consent(bng_account.consent_id, bng_account.access_token)

        db.session.delete(bng_account)
        db.session.commit()
        formatted_flash("De BNG-koppeling is verwijderd.", color="green")
        return redirect(url_for("index"))

    if not util.validate_on_submit(form, request):
        return

    if form.iban.data in [x.iban for x in BNGAccount.query.all()]:
        formatted_flash(("Het aanmaken van de BNG-koppeling is mislukt. Er bestaat al een koppeling met"
                         f"deze IBAN: {form.iban.data}."), color="red")
        return

    try:
        consent_id, oauth_url = bng.create_consent(
            iban=form.iban.data,
            valid_until=form.valid_until.data
        )
    except ConnectionError as e:
        app.logger.error(repr(e))
        formatted_flash(("Het aanmaken van de BNG-koppeling is mislukt door een verbindingsfout. De beheerder van Open "
                         "Poen is op de hoogte gesteld. Probeer het later nog eens, of neem contact op met de "
                         "beheerder."),
                        color="red")
        return

    bng_token = jwt.encode({
        'user_id': current_user.id,
        'iban': form.iban.data,
        'bank_name': 'BNG',
        'exp': time() + 1800,
        "consent_id": consent_id
    },
        app.config['SECRET_KEY'],
        algorithm='HS256'
    ).decode('utf-8')

    return redirect(oauth_url.format(bng_token))


def process_bng_callback(request):
    if not current_user.admin or not current_user.is_authenticated:
        formatted_flash("Je hebt niet voldoende rechten om een koppeling met BNG bank aan te maken.", color="red")
        return

    try:
        access_code = request.args.get("code")
        if not access_code: raise ValidationError("Toegangscode ontbreekt in callback.")
        token_info = jwt.decode(
            request.args.get("state"),
            app.config["SECRET_KEY"],
            algorithms="HS256"
        )
    except ValidationError as e:
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
        response = bng.retrieve_access_token(access_code)
        access_token, expires_in = response["access_token"], response["expires_in"]
    except ConnectionError as e:
        app.logger.error(repr(e))
        formatted_flash(("Er ging iets mis terwijl je toegang verleende aan BNG bank. De beheerder van Open Poen "
                         "is op de hoogte gesteld. Probeer het later nog eens, of neem contact op met de beheerder."),
                        color="red")
        return

    new_bng_account = BNGAccount(
        user_id=token_info["user_id"],
        consent_id=token_info["consent_id"],
        access_token=access_token,
        expires_on=datetime.now() + timedelta(seconds=int(expires_in)),
        iban=token_info["iban"]
    )
    db.session.add(new_bng_account)
    db.session.commit()
    formatted_flash("De BNG-koppeling is aangemaakt. Betalingen worden nu op de achtergrond opgehaald.", color="green")

    try:
        get_bng_payments()
    except (NotImplementedError, ValidationError, ValueError, IntegrityError) as e:
        app.logger.error(repr(e))
        formatted_flash(("Het opslaan van de betalingen is mislukt. De beheerder van Open Poen is op de hoogte "
                         "gesteld."), color="red")
        return

    return redirect(url_for("index"))


def get_days_until(date):
    # TODO: Handle timezones gracefully.
    time_left = date.replace(tzinfo=None) - datetime.now()
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
    elif len(linked_bng_accounts) == 0:
        created, created_color = "niet aangemaakt", "red"
        status, status_color = "offline", "red"
        days_left, days_left_color = 0, "red"
        # TODO Add time of last payment import.
        date_last_sync, date_last_sync_color = "12-12-2021", "green"
    else:
        bng_account = linked_bng_accounts[0]
        created_color, created = "green", "aangemaakt"
        try:
            bng_info = bng.retrieve_consent_details(
                bng_account.consent_id,
                bng_account.access_token
            )
        except ConnectionError as e:
            app.logger.error(repr(e))
            formatted_flash(("Er is een BNG-koppeling, maar de status kon niet worden opgehaald. De beheerder van "
                            "Open Poen is op de hoogte gebracht."), color="red")
            status, status_color = "red", "offline"
            days_left, days_left_color = get_days_until(bng_account.expires_on)
            # TODO Add time of last payment import.
            date_last_sync, date_last_sync_color = "12-12-2021", "green"
        else:
            status = "online" if bng_info["consentStatus"] == "valid" else "offline"
            status_color = "green" if status == "online" else "red"
            days_left, days_left_color = get_days_until(
                datetime.strptime(bng_info["validUntil"], "%Y-%m-%d")
            )
            # TODO Add time of last payment import.
            date_last_sync, date_last_sync_color = "12-12-2021", "green"

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
            "message": f"Laatst gesynchroniseerd op {date_last_sync}."
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
            card_number = re.search("6731924\d*", payment["remittance_information_structured"]).group(0)
        except AttributeError:
            card_number = None
        # To simplify things, we always save empty strings as None (NULL).
        payment = {k: (v if v != "" else None) for (k, v) in payment.items()}
        new_payments.append(Payment(
            **payment,
            route=route,
            created=datetime.now(),
            card_number=card_number,
            type="BNG"
        ))

    existing_ids = set([x.transaction_id for x in Payment.query.all()])
    new_payments = [x for x in new_payments if x.transaction_id not in existing_ids]

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
    # TODO: Error handling.
    bng_account = BNGAccount.query.all()
    if len(bng_account) > 1:
        raise NotImplementedError("Op dit moment ondersteunen we slechts één BNG-koppeling.")
    if len(bng_account) == 0:
        return
    bng_account = bng_account[0]

    account_info = bng.read_account_information(
        bng_account.consent_id,
        bng_account.access_token
    )
    if len(account_info["accounts"]) > 1:
        raise NotImplementedError("Op dit moment ondersteunen we slechts één consent per BNG-koppeling.")
    elif len(account_info["accounts"]) == 0:
        raise ValidationError("Het zou niet mogelijk moeten zijn om wel een account te hebben, maar geen consent.")

    date_from = datetime.today() - timedelta(days=1000)

    # TODO: Make this part asynchronous?
    # TODO: Do something with dateTo as well.
    # TODO: What to do with booking status? Are we interested in pending?
    # TODO: What about balance?

    with TemporaryDirectory() as d:
        with open(os.path.join(d, "transaction_list.zip"), "wb") as f:
            f.write(bng.read_transaction_list(
                bng_account.consent_id,
                bng_account.access_token,
                account_info["accounts"][0]["resourceId"],
                date_from.strftime("%Y-%m-%d"),
            ))
        with zipfile.ZipFile(os.path.join(d, "transaction_list.zip")) as z:
            z.extractall(d)
        payment_json_files = [x for x in os.listdir(d) if x.endswith(".json")]
        if len(payment_json_files) != 1:
            raise ValidationError("The downloaded transaction zip does not contain a json file.")
        with open(os.path.join(d, payment_json_files[0])) as f:
            payments = json.load(f)
            payments = payments["transactions"]["booked"]

    parse_and_save_bng_payments(payments)


def process_form(form, object):
    if not util.validate_on_submit(form, request):
        return

    if hasattr(form, "remove") and form.remove.data:
        instance = object.query.get(form.id.data)
        db.session.delete(instance)
        db.session.commit()
        util.formatted_flash("Object verwijderd.", color="green")
        return instance.redirect_after_delete

    data = {x.short_name: x.data for x in form if x.type not in fields_to_exclude}

    if hasattr(form, "id") and form.id.data is not None:
        instance = object.query.get(data["id"])
        if not instance:
            util.formatted_flash("Object bestaat niet.", color="red")
            return render_template(
                "404.html",
                use_square_borders=app.config["USE_SQURAE_BORDERS"],
                footer=app.config["FOOTER"]
            )
        try:
            instance.update(data)
            return instance.redirect_after_edit
        except (ValueError, IntegrityError) as e:
            app.logger.error(repr(e))
            db.session().rollback()
            util.formatted_flash("Object aanpassen mislukt.", color="red")
            return instance.redirect_after_edit
    else:
        try:
            instance = object.create(data)
            return instance.redirect_after_create
        except (ValueError, IntegrityError) as e:
            app.logger.error(repr(e))
            db.session().rollback()
            util.formatted_flash("Object aanmaken mislukt.", color="red")
            return
