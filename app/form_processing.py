from datetime import datetime
from flask import flash, redirect, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import os

from app import app, db
from app.forms import CategoryForm, PaymentForm, EditAttachmentForm
from app.models import Category, Payment, File, User
from app.util import flash_form_errors, form_in_request


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
    else:
        return

    payment_form.route.choices = [
        ('subsidie', 'subsidie'),
        ('inbesteding', 'inbesteding'),
        ('aanbesteding', 'aanbesteding')
    ]

    # When the user removes a manually added payment, the route selection
    # field will have no value and validate_on_submit will fail, so add a
    # default value
    if payment_form.route.data == 'None':
        payment_form.route.data = 'subsidie'

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
        flash('<span class="text-default-red">Er ging iets fout bij het aanpassen van de betaling. Ga hiernaartoe terug en volg de aanwijzingen op.</span>')
        return payment_form


# Populate the payment forms which allows the user to edit it
def create_payment_forms(payments, project_owner):
    payment_forms = {}
    for payment in payments:
        # If a payment already contains a category, retrieve it to set
        # this category as the selected category in the drop-down menu
        selected_category = ''
        if payment.category:
            selected_category = payment.category.id
        payment_form = PaymentForm(prefix=f'payment_form_{payment.id}', **{
            'short_user_description': payment.short_user_description,
            'long_user_description': payment.long_user_description,
            'created': payment.created,
            'id': payment.id,
            'hidden': payment.hidden,
            'category_id': selected_category,
            'route': payment.route
        })

        # The created field may only be edited on manually added transactions
        if payment.type != 'MANUAL':
            del payment_form['created']

        # A project with subprojects can contain multiple editable
        # payments on the project page, so we need to retrieve the
        # categories for each payment (could be made more efficient,
        # but this is readable)
        if payment.subproject:
            payment_form.category_id.choices = payment.subproject.make_category_select_options()
        else:
            payment_form.category_id.choices = payment.project.make_category_select_options()

        payment_form.route.choices = [
            ('subsidie', 'subsidie'),
            ('inbesteding', 'inbesteding'),
            ('aanbesteding', 'aanbesteding')
        ]

        # Only allow manually added payments to be removed
        if payment.type != 'MANUAL':
            del payment_form.remove

        # Only allow project owners to hide a transaction
        if project_owner:
            payment_form.hidden = payment.hidden

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
