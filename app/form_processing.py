from datetime import datetime
from flask import flash, redirect, url_for, request
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import os

from wtforms.validators import ValidationError

from app import app, db
from app.forms import CategoryForm, NewPaymentForm, PaymentForm, EditAttachmentForm
from app.models import Category, Payment, File, User, Subproject
from app.util import flash_form_errors, form_in_request, formatted_flash
from app import util
from app import bng as bng

import jwt
from flask_login import current_user
from time import time

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
        if project.contains_subprojects:
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
    if not util.validate_on_submit(form, request) or not current_user.admin:
        return None
    
    consent_id, oauth_url = bng.create_consent(
        iban=form.iban.data,
        valid_until=form.valid_until.data
    )

    # TODO: What if the API returns an error code?

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
    if not current_user.admin:
        # TODO Error handling.
        return None
    
    try:
        access_code = request.args.get("code")
        token_info = jwt.decode(
            request.args.get("state"),
            app.config["SECRET_KEY"],
            algorithms="HS256"
        )
    except Exception as e:
        # TODO Error handling.
        # Token is still decoded when user went back / cancelled.
        pass 
    
    try:
        access_token = bng.retrieve_access_token(access_code)
    except Exception as e:
        # TODO Error handling. (User went back / cancelled.)
        pass

    # TODO: Now save consent_id and access_token to the database. (And expires in!)
