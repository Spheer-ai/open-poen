from datetime import datetime, timedelta
from flask import flash, redirect, url_for, request
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import os

from wtforms.validators import ValidationError

from app import app, db
from app.forms import CategoryForm, NewPaymentForm, PaymentForm, EditAttachmentForm
from app.models import Category, Payment, File, User, Subproject, BNGAccount
from app.util import flash_form_errors, form_in_request, format_currency, formatted_flash
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
            payment_form.category_id.choices = temppayment.project.make_category_select_options()

        # Make sure the user is allowed to edit this payment
        # (especially needed when a normal users edits a subproject
        # payment on a project page)
        if not project_owner and not temppayment.subproject.id in user_subproject_ids:
            return
        # Make sure the transaction amount can't be changed if the transaction is not manual.
        if temppayment.type != "MANUAL":
            payment_form.amount_value.data = temppayment.amount_value
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
            new_payment_data = {}
            for f in payment_form:
                if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                    # If the category is edited to be empty again, make
                    # sure to set it to None instead of ''
                    if f.short_name == 'category_id':
                        if f.data == '':
                            new_payment_data[f.short_name] = None
                        else:
                            new_payment_data[f.short_name] = f.data
                    else:
                        new_payment_data[f.short_name] = f.data

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
            'amount_value': payment.amount_value,
            'id': payment.id,
            'hidden': payment.hidden,
            'category_id': "" if payment.category is None else payment.category.id,
            'route': payment.route
        })

        if payment.type != 'MANUAL':
            del payment_form['created']
            del payment_form['remove']

        if payment.subproject:
            payment_form.category_id.choices = payment.subproject.make_category_select_options()
        else:
            payment_form.category_id.choices = payment.project.make_category_select_options()

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
def process_transaction_attachment_form(request, transaction_attachment_form, project_owner, user_subproject_ids, project_id=0, subproject_id=0):
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

            save_attachment(transaction_attachment_form.data_file.data, transaction_attachment_form.mediatype.data, payment, 'transaction-attachment')

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


def process_subproject_form(form):
    """Returns a truthy value in the form of a redirect or None when no redirect
    is necessary."""

    if form.id.data and form.project_id.data:
        action = "UPDATE"
    elif not form.id.data and form.project_id.data:
        action = "CREATE"
    else:
        action = None
    if form.remove.data:
        action = "DELETE"

    if action == "DELETE":
        Subproject.query.filter_by(id=form.id.data).delete()
        db.session.commit()
        formatted_flash('Subproject "%s" is verwijderd' % form.name.data, color="green")
        return redirect(url_for("project", project_id=form.project_id.data))
    
    if not util.validate_on_submit(form, request):
        return None
    
    new_subproject_data = {}
    for f in form:
        if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
            new_subproject_data[f.short_name] = f.data
    name, iban = new_subproject_data['name'], new_subproject_data['iban']

    if action == "CREATE":
        try:
            subproject = Subproject(**new_subproject_data)
            db.session.add(subproject)
            db.session.commit()
        except (ValueError, IntegrityError) as e:
            db.session().rollback()
            app.logger.error(repr(e))
            # TODO: BNG
            formatted_flash("Subproject toevoegen mislukt: naam {name} en/of IBAN {iban} bestaan al.", color="red")
        return redirect(url_for("project", project_id=form.project_id.data))
    if action == "UPDATE":
        try:
            subprojects = Subproject.query.filter_by(
                id=form.id.data
            )
            if len(subprojects.all()):
                subprojects.update(new_subproject_data)
                db.session.commit()
                name = new_subproject_data["name"]
                formatted_flash(f'Subproject {name} is bijgewerkt</span>', color="green")
        except (ValueError, IntegrityError) as e:
            db.session().rollback()
            app.logger.error(repr(e))
            # TODO: BNG
            formatted_flash("Subproject bijwerken mislukt: naam {name} en/of IBAN {iban} bestaan al.", color="red")
        return redirect(url_for(
            "subproject",
            project_id=form.project_id.data,
            subproject_id=form.id.data
        ))
    
    if action is None:
        raise ValidationError("No action taken for submitted valid subproject form.")


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
        raise ValidationError(("Cannot create a payment form for a project ",
                                "and a subproject at once."))

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


def process_bng_link_form(form):
    if not current_user.is_authenticated or not current_user.admin:
        return None

    if form.remove.data:
        # This should always result in one account for now. Eventually we might
        # want to support multiple BNG accounts per user, but we'll have to implement
        # this later.
        bng_account = BNGAccount.query.filter_by(user_id=current_user.id).all()
        if len(bng_account) > 1:
            raise NotImplementedError("A user should not be able to have more than one BNG account.")
        if len(bng_account) == 0:
            raise ValidationError("A user shouldn't be able to click remove if there is no BNG account linked.")
        bng_account = bng_account[0]

        # TODO: This returns a 401 now for the Sandbox, but I don't see how there is
        # anything wrong with my request.
        # bng.delete_consent(bng_account.consent_id, bng_account.access_token)

        db.session.delete(bng_account)
        db.session.commit()
        # TODO: Revoke consent with BNG's API.
        formatted_flash("BNG-koppeling is verwijderd.", color="green")
        return redirect(url_for("index"))

    if not util.validate_on_submit(form, request):
        return

    if form.iban.data in [x.iban for x in BNGAccount.query.all()]:
        formatted_flash(f"Het aanmaken van de BNG-koppeling is mislukt. Er bestaat al een koppeling met deze IBAN: {form.iban.data}.", color="red")
        return
    
    try:
        consent_id, oauth_url = bng.create_consent(
            iban=form.iban.data,
            valid_until=form.valid_until.data
        )
    except Exception as e:
        formatted_flash(f"De aanvraag bij BNG bank is mislukt. De foutcode is: {e}", color="red")
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
        formatted_flash(f"Er ging iets mis terwijl je toegang verleende aan BNG bank. De foutcode is: {e}", color="red")
        return
    
    try:
        response = bng.retrieve_access_token(access_code)
        access_token, expires_in = response["access_token"], response["expires_in"]
    except Exception as e:
        formatted_flash("Het ophalen van de toegangscode voor de koppeling met BNG bank is mislukt.", color="red")
        return

    try:
        new_bng_account = BNGAccount(
            user_id=token_info["user_id"],
            consent_id = token_info["consent_id"],
            access_token = access_token,
            expires_on = datetime.now() + timedelta(seconds=int(expires_in)),
            iban = token_info["iban"]
        )
        db.session.add(new_bng_account)
        db.session.commit()
        payments = get_bng_payments()
        process_bng_payments(payments)
        formatted_flash("BNG-koppeling succesvol aangemaakt. Betalingen worden nu op de achtergrond opgehaald.", color="green")
        return redirect(url_for("index"))
    except (ValidationError, NotImplementedError, IntegrityError, ValueError) as e:
        formatted_flash(f"Aanmaken BNG-koppeling mislukt. De foutcode is: {e}", color="red")
    

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


def get_bng_info(bng_account):
    try:
        bng_info = bng.retrieve_consent_details(
            bng_account.consent_id,
            bng_account.access_token
        )
    except ConnectionError as e:
        formatted_flash("Er is een BNG-koppeling, maar deze is offline.", color="red")
        days_left, days_left_color = get_days_until(bng_account.expires_on)
        date_last_sync = "12-12-2021"  #TODO Add time of last payment import.

        return {
            "status": {
                "color": "red",
                "message": "Koppeling is offline."
            },
            "days_left": {
                "color": days_left_color,
                "message": f"Nog {days_left} dagen geldig."
            },
            "sync" : {
                "color": "green",
                "message": f"Laatst gesynchroniseerd op {date_last_sync}."
            }
        }
    
    days_left, days_left_color = get_days_until(
        datetime.strptime(bng_info["validUntil"], "%Y-%m-%d")
    )
    date_last_sync = "12-12-2021"  #TODO Add time of last payment import.

    return {
        "status": {
            "color": "green",
            "message": "Koppeling is online."
        },
        "days_left": {
            "color": days_left_color,
            "message": f"Nog {days_left} dagen geldig."
        },
        "sync" : {
            "color": "green",
            "message": f"Laatst gesynchroniseerd op {date_last_sync}."
        }
    }


def get_bng_payments():
    # TODO: Error handling.
    bng_account = BNGAccount.query.all()
    if len(bng_account) > 1:
        raise NotImplementedError("At this moment, we only support a coupling with a single BNG account.")
    if len(bng_account) == 0:
        return
    bng_account = bng_account[0]

    account_info = bng.read_account_information(
        bng_account.consent_id,
        bng_account.access_token
    )    
    if len(account_info["accounts"]) > 1:
        raise NotImplementedError("At this moment, we only support consents for a single account.")
    elif len(account_info["accounts"]) == 0:
        raise ValidationError("It should not be possible to have consent, but to not have an account associated with it.")

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

    return payments


def flatten(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def process_bng_payments(payments):
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
        new_payments.append(Payment(
            **payment,
            route=route,
            created=datetime.now()
        ))
    
    # TODO: Check for already existing payments.

    try:
        db.session.bulk_save_objects(new_payments)
        db.session.commit()
        # TODO: Log this.
    except (ValueError, IntegrityError) as e:
        db.session.rollback()
        app.logger.error(repr(e))
        raise
