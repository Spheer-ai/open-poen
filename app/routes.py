from flask import (
    render_template, redirect, url_for, flash, request,
    send_from_directory
)
from flask_login import login_required, login_user, logout_user, current_user

from app import app, db
from app.forms import (
    ResetPasswordRequestForm, ResetPasswordForm, LoginForm, ProjectForm,
    SubprojectForm, TransactionAttachmentForm,
    EditAttachmentForm, FunderForm, AddUserForm, EditAdminForm,
    EditProjectOwnerForm, EditUserForm, EditProfileForm, CategoryForm,
    NewPaymentForm, PaymentForm
)
from app.email import send_password_reset_email
from app.models import (
    User, Project, Subproject, Payment, UserStory, IBAN, File, Funder, Category
)
from app.form_processing import (
    process_category_form, process_payment_form, create_payment_forms,
    process_transaction_attachment_form, create_edit_attachment_forms,
    process_edit_attachment_form, save_attachment, process_subproject_form
)
from sqlalchemy.exc import IntegrityError

from datetime import datetime
import json
from app import util


# Add 'Cache-Control': 'private' header if users are logged in
@app.after_request
def after_request_callback(response):
    if current_user.is_authenticated:
        response.headers['Cache-Control'] = 'private'

    return response


# Things to do before every request is processed
@app.before_request
def before_request():
    # Check if the current user is still active before every request. If
    # an admin/project owner sets a user to inactive then the user will
    # be logged out when it tries to make a new request.
    if current_user.is_authenticated and not current_user.is_active():
        flash(
            '<span class="text-default-red">Deze gebruiker is niet meer '
            'actief</span>'
        )
        logout_user()
        return redirect(url_for('index'))

    # If the current user has no first name, last name or biography then
    # send them to their profile page where they can add them
    if current_user.is_authenticated and request.path != '/profiel-bewerken':
        if (not current_user.first_name
                or not current_user.last_name or not current_user.biography):
            flash(
                '<span class="text-default-red">Sommige velden in uw profiel zijn nog '
                'niet ingevuld. Vul deze in om verder te kunnen gaan.</span>'
            )
            return redirect(url_for('profile_edit'))


@app.route("/", methods=['GET', 'POST'])
def index():
    modal_id = None

    # Process filled in edit admin form
    edit_admin_form = EditAdminForm(prefix="edit_admin_form")

    # Update admin
    if util.validate_on_submit(edit_admin_form, request):
        admins = User.query.filter_by(id=edit_admin_form.id.data)
        new_admin_data = {}
        for f in edit_admin_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_admin_data[f.short_name] = f.data

        # Update if the admin exists
        if len(admins.all()):
            admins.update(new_admin_data)
            db.session.commit()
            flash('<span class="text-default-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(url_for('index'))
    else:
        util.flash_form_errors(edit_admin_form, request)

    # Populate the edit admin forms which allows the user to edit it
    edit_admin_forms = {}
    for admin in User.query.filter_by(admin=True).order_by('email'):
        edit_admin_forms[admin.email] = EditAdminForm(
            prefix="edit_admin_form", **{
                'admin': admin.admin,
                'active': admin.active,
                'id': admin.id
            }
        )

    # Process filled in add user form
    add_user_form = AddUserForm(prefix="add_user_form")

    # Add user (either admin or project owner)
    if util.validate_on_submit(add_user_form, request):
        new_user_data = {}
        for f in add_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_user_data[f.short_name] = f.data

        try:
            util.add_user(**new_user_data)
            flash(
                '<span class="text-default-green">"%s" is uitgenodigd als admin of '
                'project owner (of toegevoegd als admin of project owner als de '
                'gebruiker al bestond)' % (
                    new_user_data['email']
                )
            )
        except ValueError as e:
            flash(str(e))

        # redirect back to clear form data
        return redirect(url_for('index'))
    else:
        util.flash_form_errors(add_user_form, request)

    # Create an empty form, or fill it with a submitted form so that we can
    # return the validated version. modal_id is used to pop open the modal
    # on loading the page, if it contains a validated form.
    project_form = ProjectForm(prefix="project_form")
    # Save (i.e. create) project
    if util.validate_on_submit(project_form, request):
        new_project_data = {}
        for f in project_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_project_data[f.short_name] = f.data

        try:
            # IBAN can't be set during initial creation of a new
            # project so remove it
            new_project_data.pop('iban')
            project = Project(**new_project_data)
            db.session.add(project)
            db.session.commit()
            flash(
                '<span class="text-default-green">Project "%s" is '
                'toegevoegd</span>' % (
                    new_project_data['name']
                )
            )
        except IntegrityError as e:
            db.session().rollback()
            app.logger.error(repr(e))
            flash(
                '<span class="text-default-red">Project toevoegen mislukt: '
                'naam "%s" bestaat al, kies een andere naam <span>' % (
                    new_project_data['name']
                )
            )
        # redirect back to clear form data
        return redirect(url_for('index'))
    else:
        if len(project_form.errors) > 0:
            modal_id = ["#modal-project-toevoegen"]

    # Calculate amounts awarded and spent
    # total_awarded = all current project balances
    #               + abs(all spent project amounts)
    #               - all amounts received from own subprojects (in the
    #                 case the didn't spend all their money and gave it
    #                 back)
    # total_spent = abs(all spend subproject amounts)
    #             - all amounts paid back by suprojects to their project
    total_awarded = 0
    total_spent = 0
    project_data = []
    # Retrieve data for each project
    for project in Project.query.all():
        project_owner = False
        if current_user.is_authenticated and (
            current_user.admin or project.has_user(current_user.id)
        ):
            project_owner = True

        if project.hidden and not project_owner:
            continue

        # Retrieve the amounts for this project
        amounts = util.calculate_project_amounts(project.id)
        # Use budget for the awarded amount if available
        if project.budget:
            total_awarded += project.budget
        else:
            total_awarded += amounts['awarded']
        total_spent += amounts['spent']
        budget = ''
        if project.budget:
            budget = util.format_currency(project.budget)

        project_data.append(
            {
                'id': project.id,
                'name': project.name,
                'hidden': project.hidden,
                'project_owner': project_owner,
                'amounts': amounts,
                'budget': budget
            }
        )

    return render_template(
        'index.html',
        background=app.config['BACKGROUND'],
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        tagline=app.config['TAGLINE'],
        footer=app.config['FOOTER'],
        project_data=project_data,
        total_awarded_str=util.human_format(total_awarded),
        total_spent_str=util.human_format(total_spent),
        project_form=project_form,
        add_user_form=AddUserForm(prefix='add_user_form'),
        edit_admin_forms=edit_admin_forms,
        user_stories=UserStory.query.all(),
        modal_id=json.dumps(modal_id)  # Does nothing if None. Loads the modal
        # on page load if supplied.
    )


@app.route("/project/<project_id>", methods=['GET', 'POST'])
def project(project_id):
    modal_id = None
    payment_id = None

    project = Project.query.get(project_id)

    if not project:
        return render_template(
            '404.html',
            use_square_borders=app.config['USE_SQUARE_BORDERS'],
            footer=app.config['FOOTER']
        )

    # A project owner is either an admin or a user that is part of this
    # project
    project_owner = False
    if current_user.is_authenticated and (
        current_user.admin or project.has_user(current_user.id)
    ):
        project_owner = True

    if project.hidden and not project_owner:
        return render_template(
            '404.html',
            use_square_borders=app.config['USE_SQUARE_BORDERS'],
            footer=app.config['FOOTER']
        )

    # Process filled in funder form.
    funder_form = FunderForm(prefix="funder_form")

    # Remove funder
    if funder_form.remove.data:
        Funder.query.filter_by(id=funder_form.id.data).delete()
        db.session.commit()
        flash(
            '<span class="text-default-green">Sponsor "%s" is verwijderd</span>' % (
                funder_form.name.data
            )
        )
        # redirect back to clear form data
        return redirect(url_for('project', project_id=project_id))

    # Save or update funder
    if util.validate_on_submit(funder_form, request):
        funders = Funder.query.filter_by(id=funder_form.id.data)
        new_funder_data = {}
        for f in funder_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_funder_data[f.short_name] = f.data

        # Update if the funder already exists
        if len(funders.all()):
            funders.update(new_funder_data)
            db.session.commit()
            flash(
                '<span class="text-default-green">Sponsor "%s" is '
                'bijgewerkt</span>' % (
                    new_funder_data['name']
                )
            )
        # Otherwise, save a new funder
        else:
            funder = Funder(**new_funder_data)
            funder.project_id = project_id
            db.session.add(funder)
            db.session.commit()
            flash(
                '<span class="text-default-green">Sponsor "%s" is '
                'toegevoegd</span>' % (
                    new_funder_data['name']
                )
            )

        # redirect back to clear form data
        return redirect(url_for('project', project_id=project_id))
    else:
        util.flash_form_errors(funder_form, request)

    # Populate the funder forms which allows the user to edit
    # it
    funder_forms = []
    for funder in project.funders:
        funder_forms.append(
            FunderForm(prefix=f"funder_form", **{
                'name': funder.name,
                'url': funder.url,
                'id': funder.id
            })
        )



    subproject_form = SubprojectForm(prefix="subproject_form")
    form_redirect = process_subproject_form(subproject_form)
    if form_redirect:
        return form_redirect
    if len(subproject_form.errors) > 0:
        modal_id = ["#subproject-toevoegen"]
    else:
        subproject_form = SubprojectForm(prefix="subproject_form", **{
            'project_id': project.id
        })

    # Retrieve any subprojects a normal logged in user is part of
    user_subproject_ids = []
    if project.contains_subprojects and current_user.is_authenticated and not project_owner:
        for subproject in project.subprojects:
            if subproject.has_user(current_user.id):
                user_subproject_ids.append(subproject.id)

    new_payment_form = ''
    # Filled with all categories for each subproject; used by some JavaScript
    # to update the categories in the Select field when the user selects
    # another subproject to add the new payment to
    categories_dict = {}
    # Process/create new payment form (added manually by a project owner)
    if project_owner:
        # Process filled in new payment form
        new_payment_form = NewPaymentForm(prefix="new_payment_form")
        # Add subprojects that the user has access to
        if project.contains_subprojects:
            initialized_first_subproject_categories = False
            for subproject in project.subprojects:
                categories_dict[subproject.id] = subproject.make_category_select_options()
                new_payment_form.subproject_id.choices.append(
                    (subproject.id, subproject.name)
                )
                if not initialized_first_subproject_categories:
                    new_payment_form.category_id.choices = categories_dict[subproject.id]
                    initialized_first_subproject_categories = True

        else:
            del new_payment_form.subproject_id

        # Somehow we need to repopulate the category_id.choices with the same
        # values as used when the form was generated. Probably to validate
        # if the selected value is valid.
        if new_payment_form.subproject_id and new_payment_form.subproject_id.data != 'None':
            tempsubproject = Subproject.query.filter_by(
                id=new_payment_form.subproject_id.data
            ).first()
            if tempsubproject:
                new_payment_form.category_id.choices = tempsubproject.make_category_select_options()
        else:
            new_payment_form.category_id.choices = project.make_category_select_options()

        # Save new payment
        if util.validate_on_submit(new_payment_form, request):
            new_payment_data = {}
            for f in new_payment_form:
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

            new_attachment = {
                "mediatype": new_payment_data.pop("mediatype"),
                "data_file": new_payment_data.pop("data_file")
            }

            new_payment = Payment(**new_payment_data)

            # A payment can only be linked to a project or a subproject,
            # so only add a project_id if this project doesn't contain
            # subprojects
            if not project.contains_subprojects:
                new_payment.project_id = project_id

            new_payment.amount_currency = 'EUR'
            new_payment.type = 'MANUAL'
            new_payment.updated = datetime.now()
            db.session.add(new_payment)
            db.session.commit()
            flash(
                '<span class="text-default-green">Transactie is toegevoegd</span>'
            )

            if new_attachment["data_file"] is not None:
                save_attachment(
                    new_attachment["data_file"],
                    new_attachment["mediatype"],
                    new_payment,
                    'transaction-attachment'
                )

            # redirect back to clear form data
            return redirect(url_for('project', project_id=project_id))
        
        # Open up again the adding a payment modal in case of errors after validation.
        # NOTE: This works as intended because we only validate if the request contains
        # the new_payment_form form.
        else:
            if len(new_payment_form.errors) > 0:
                modal_id = ["#modal-transactie-toevoegen"]

    # Process/create (filled in) payment form
    payment_forms = {}
    transaction_attachment_form = ''
    edit_attachment_forms = {}
    edit_attachment_form = ''
    if project_owner or user_subproject_ids:
        # Process filled in payment form
        payment_form_return = process_payment_form(request, project, project_owner, user_subproject_ids, is_subproject=False)
        if payment_form_return and type(payment_form_return) != PaymentForm:
            return payment_form_return

        # Populate the payment forms which allows the user to edit it
        editable_payments = []
        editable_attachments = []
        if project.contains_subprojects:
            if project_owner:
                editable_payments += project.payments
                for payment in project.payments:
                    editable_attachments += payment.attachments
            for subproject in project.subprojects:
                if project_owner:
                    editable_payments += subproject.payments
                    for payment in subproject.payments:
                        editable_attachments += payment.attachments
                # If the user is not an admin/project owner then only allow it
                # to edit payments from its subprojects
                elif user_subproject_ids:
                    for payment in subproject.payments:
                        if payment.subproject_id in user_subproject_ids:
                            editable_payments.append(payment)
                            editable_attachments.append(payment.attachment)
        else:
            editable_payments = project.payments
            for payment in project.payments:
                editable_attachments += payment.attachments
        
        if type(payment_form_return) == PaymentForm:
            payment_id = payment_form_return.id.data
            editable_payments = [x for x in editable_payments if x.id != payment_form_return.id.data]

        payment_forms = create_payment_forms(
            editable_payments,
            project_owner
        )

        if type(payment_form_return) == PaymentForm:
            payment_forms[payment_form_return.id.data] = payment_form_return

        # Process new transaction attachment form
        transaction_attachment_form = TransactionAttachmentForm(
            prefix="transaction_attachment_form"
        )
        transaction_attachment_form_return = process_transaction_attachment_form(
            request,
            transaction_attachment_form,
            project_owner,
            user_subproject_ids,
            project.id
        )
        if transaction_attachment_form_return:
            return transaction_attachment_form_return

        # Process transaction attachment edit form
        edit_attachment_form = EditAttachmentForm(
            prefix="edit_attachment_form"
        )
        edit_attachment_form_return = process_edit_attachment_form(
            request,
            edit_attachment_form,
            project.id,
        )
        if edit_attachment_form_return:
            return edit_attachment_form_return

        # Fill in attachment form data which allow a user to edit it
        edit_attachment_forms = create_edit_attachment_forms(editable_attachments)

    payments = []
    if project.contains_subprojects:
        payments += project.payments
        for subproject in project.subprojects:
            payments += subproject.payments
    else:
        payments += project.payments

    # Process filled in edit project owner form
    edit_project_owner_form = EditProjectOwnerForm(
        prefix="edit_project_owner_form"
    )

    # Update project owner
    if util.validate_on_submit(edit_project_owner_form, request):
        edited_project_owner = User.query.filter_by(
            id=edit_project_owner_form.id.data
        )
        new_project_owner_data = {}
        remove_from_project = False
        remove_from_project_id = 0
        for f in edit_project_owner_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'remove_from_project':
                    remove_from_project = f.data
                elif f.short_name == 'project_id':
                    remove_from_project_id = f.data
                else:
                    new_project_owner_data[f.short_name] = f.data

        # Update if the project owner exists
        if len(edited_project_owner.all()):
            edited_project_owner.update(new_project_owner_data)
            if remove_from_project:
                # We need to get the user using '.first()' otherwise we
                # can't remove the project because of garbage collection
                edited_project_owner = edited_project_owner.first()
                edited_project_owner.projects.remove(
                    Project.query.get(remove_from_project_id)
                )

            db.session.commit()
            flash('<span class="text-default-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(url_for('project', project_id=project.id))
    else:
        if len(edit_project_owner_form.errors) > 0:
            modal_id = ["#project-bewerken", "#project-owner-toevoegen"]

    # Populate the edit project owner forms which allows the user to
    # edit it
    edit_project_owner_forms = {}
    temp_edit_project_owner_forms = {}
    for project_owner in project.users:
        temp_edit_project_owner_forms[project_owner.email] = (
            EditProjectOwnerForm(
                prefix="edit_project_owner_form", **{
                    'hidden': project_owner.hidden,
                    'active': project_owner.active,
                    'id': project_owner.id,
                    'project_id': project.id
                }
            )
        )
    edit_project_owner_forms[project.id] = temp_edit_project_owner_forms

    # Process filled in add user form
    add_user_form = AddUserForm(prefix="add_user_form")

    # Add user (either admin or project owner)
    if util.validate_on_submit(add_user_form, request):
        new_user_data = {}
        for f in add_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_user_data[f.short_name] = f.data

        try:
            util.add_user(**new_user_data)
            flash(
                '<span class="text-default-green">"%s" is uitgenodigd als admin of '
                'project owner (of toegevoegd als admin of project owner als de '
                'gebruiker al bestond)' % (
                    new_user_data['email']
                )
            )
        except ValueError as e:
            flash(str(e))

        # redirect back to clear form data
        return redirect(url_for('project', project_id=project.id))
    else:
        if len(add_user_form.errors) > 0:
            modal_id = ["#project-bewerken", "#project-owner-toevoegen"]

    # Process filled in project form
    project_form = ProjectForm(prefix="project_form")

    # Remove project
    if project_form.remove.data and current_user.admin:
        Project.query.filter_by(id=project.id).delete()
        db.session.commit()
        flash(
            '<span class="text-default-green">Project "%s" is verwijderd</span>' % (
                project.name
            )
        )
        # redirect back to clear form data
        return redirect(url_for('index'))

    # Save or update project
    # Somehow we need to repopulate the iban.choices with the same
    # values as used when the form was generated for this project.
    # Probably to validate if the selected value is valid.
    if util.form_in_request(project_form, request):
        if request.method == 'POST' and project_form.name.data:
            projects = Project.query.filter_by(id=project_form.id.data)
            # TODO: Implement logic to be able to link passes to a project.

    if util.validate_on_submit(project_form, request):
        new_project_data = {}
        for f in project_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'iban':
                    # TODO: Implement logic to link a project to BNG.
                    pass
                else:
                    new_project_data[f.short_name] = f.data

        try:
            # Update if the project already exists
            if len(projects.all()):
                # We don't allow editing of the 'contains_subprojects' value after a project is created
                del new_project_data['contains_subprojects']

                # TODO: Ensure that the same passes can't be linked to multiple projects.

                # TODO: Ensure that when a pass is edited or removed, the list of payments
                # belonging to the project are updated.

                projects.update(new_project_data)
                db.session.commit()

                flash(
                    '<span class="text-default-green">Project "%s" is '
                    'bijgewerkt</span>' % (
                        new_project_data['name']
                    )
                )
            # Otherwise, save a new project
            else:
                new_project = Project(**new_project_data)
                db.session.add(new_project)
                db.session.commit()
                flash(
                    '<span class="text-default-green">Project "%s" is '
                    'toegevoegd</span>' % (
                        new_project_data['name']
                    )
                )
        except (ValueError, IntegrityError) as e:
            db.session().rollback()
            app.logger.error(repr(e))
            flash(
                '<span class="text-default-red">Project toevoegen/bijwerken mislukt: '
                'naam "%s" en/of IBAN "%s" bestaan al, kies een andere naam '
                'en/of IBAN<span>' % (
                    new_project_data['name'],
                    new_project_data['iban']
                )
            )
        # redirect back to clear form data
        return redirect(url_for('project', project_id=project.id))
    else:
        if len(project_form.errors) > 0:
            modal_id = ["#project-bewerken"]

    # Process filled in category form
    category_form = ''
    category_form_return = process_category_form(request)
    if category_form_return:
        return category_form_return

    # Retrieve data for each project
    project_data = {}
    project_owner = False
    if current_user.is_authenticated and (
        current_user.admin or project.has_user(current_user.id)
    ):
        project_owner = True

    already_authorized = False
    bunq_token = ''
    form = ''

    if project_owner:
        # TODO Logic to define already_authorized to indicate if the
        # project already has passes linked to it.

        # TODO? Generate state token for BNG.

        # Populate the project's form which allows the user to edit
        # it
        if len(project_form.errors) > 0:
            form = project_form
        else:
            form = ProjectForm(prefix="project_form", **{
                'name': project.name,
                'description': project.description,
                'hidden': project.hidden,
                'hidden_sponsors': project.hidden_sponsors,
                'budget': project.budget,
                'id': project.id,
                'contains_subprojects': project.contains_subprojects
            })
        # We don't allow editing of the 'contains_subprojects'
        # value after a project is created, but we do need to pass the
        # value in the form, so simply disable it
        # TODO: This will no also disable it when the form is returned
        # with errors, right? Fix this.
        form.contains_subprojects.render_kw = {'disabled': ''}

        # TODO: If this project is BNG enabled, allow the user to add, remove
        # or change passes.

    # Populate the category forms which allows the user to
    # edit it
    category_forms = []
    if not project.contains_subprojects:
        for category in Category.query.filter_by(
                project_id=project.id).order_by('name'):
            category_forms.append(
                CategoryForm(
                    prefix="category_form", **{
                        'id': category.id,
                        'name': category.name,
                        'project_id': project.id
                    }
                )
            )

    # Retrieve the amounts for this project
    amounts = util.calculate_project_amounts(project.id)

    project_data = {
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'hidden': project.hidden,
        'hidden_sponsors': project.hidden_sponsors,
        'already_authorized': already_authorized,
        'bunq_token': bunq_token,  # TODO Remove?
        'iban': project.iban,  # TODO Remove?
        'iban_name': project.iban_name,  # TODO Remove?
        'bank_name': project.bank_name,  # TODO Remove?
        'amounts': amounts,
        'form': form,
        'contains_subprojects': project.contains_subprojects,
        'category_forms': category_forms,
        'category_form': CategoryForm(prefix="category_form", **{'project_id': project.id})
    }

    # TODO: BNG base url
    base_url_auth = ""

    budget = ''
    if project.budget:
        budget = util.format_currency(project.budget)

    return render_template(
        'project.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER'],
        project=project,
        project_data=project_data,
        amounts=amounts,
        budget=budget,
        payments=payments,
        project_form=project_form,
        edit_project_owner_forms=edit_project_owner_forms,
        add_user_form=add_user_form,
        subproject_form=subproject_form,
        new_payment_form=new_payment_form,
        categories_dict=categories_dict,
        payment_forms=payment_forms,
        transaction_attachment_form=transaction_attachment_form,
        edit_attachment_forms=edit_attachment_forms,
        funder_forms=funder_forms,
        new_funder_form=funder_form,
        project_owner=project_owner,
        user_subproject_ids=user_subproject_ids,
        timestamp=util.get_export_timestamp(),
        server_name=app.config['SERVER_NAME'],  # TODO Remove or edit
        bunq_client_id=app.config['URL_PREFIX'],  # TODO Remove or edit
        base_url_auth=base_url_auth,
        modal_id=json.dumps(modal_id),
        payment_id=json.dumps(payment_id)
    )


@app.route(
    "/project/<project_id>/subproject/<subproject_id>", methods=['GET', 'POST']
)
def subproject(project_id, subproject_id):
    modal_id = None
    payment_id = None
    subproject = Subproject.query.get(subproject_id)

    if not subproject:
        return render_template(
            '404.html',
            use_square_borders=app.config['USE_SQUARE_BORDERS'],
            footer=app.config['FOOTER']
        )

    # Check if the user is logged in and is part of this subproject
    user_in_subproject = False
    if current_user.is_authenticated and subproject.has_user(current_user.id):
        user_in_subproject = True

    # A project owner is either an admin or a user that is part of the
    # project where this subproject belongs to
    project_owner = False
    if current_user.is_authenticated and (
        current_user.admin or subproject.project.has_user(current_user.id)
    ):
        project_owner = True

    if subproject.hidden and not project_owner and not user_in_subproject:
        return render_template(
            '404.html',
            use_square_borders=app.config['USE_SQUARE_BORDERS'],
            footer=app.config['FOOTER']
        )


    subproject_form = SubprojectForm(prefix="subproject_form")
    form_redirect = process_subproject_form(subproject_form)
    if form_redirect:
        return form_redirect
    if len(subproject_form.errors) > 0:
        modal_id = ["#subproject-bewerken"]
    else:    
        subproject_form = SubprojectForm(prefix='subproject_form', **{
            'name': subproject.name,
            'description': subproject.description,
            'hidden': subproject.hidden,
            'budget': subproject.budget,
            'project_id': subproject.project.id,
            'id': subproject.id
        })

    # Retrieve the subproject id a normal logged in user is part of
    user_subproject_ids = []
    if current_user.is_authenticated and not project_owner:
        if subproject.has_user(current_user.id):
            user_subproject_ids.append(subproject.id)

    new_payment_form = ''
    # Process/create new payment form (added manually by a user)
    if project_owner:
        # Process filled in new payment form
        new_payment_form = NewPaymentForm(prefix="new_payment_form")
        # The subproject field is only required when adding a payment on a
        # project page
        del new_payment_form.subproject_id

        # Somehow we need to repopulate the category_id.choices with the same
        # values as used when the form was generated. Probably to validate
        # if the selected value is valid. We don't know the subproject in the
        # case of an edited payment on a project page which contains subprojects,
        # so we need to retrieve this before running validate_on_submit
        new_payment_form.category_id.choices = subproject.make_category_select_options()

        # Save new payment
        if util.validate_on_submit(new_payment_form, request):
            new_payment_data = {}
            for f in new_payment_form:
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

            new_attachment = {
                "mediatype": new_payment_data.pop("mediatype"),
                "data_file": new_payment_data.pop("data_file")
            }

            new_payment = Payment(**new_payment_data)
            new_payment.subproject_id = subproject.id
            new_payment.amount_currency = 'EUR'
            new_payment.type = 'MANUAL'
            new_payment.updated = datetime.now()
            db.session.add(new_payment)
            db.session.commit()
            flash(
                '<span class="text-default-green">Transactie is toegevoegd</span>'
            )

            if new_attachment["data_file"] is not None:
                save_attachment(
                    new_attachment["data_file"],
                    new_attachment["mediatype"],
                    new_payment,
                    'transaction-attachment'
                )

            # redirect back to clear form data
            return redirect(url_for('subproject', project_id=subproject.project.id, subproject_id=subproject_id))
        else:
            if len(new_payment_form.errors) > 0:
                modal_id = ["#transactie-toevoegen"]

    # Process filled in payment form
    payment_form_return = process_payment_form(request, subproject, project_owner, user_subproject_ids, is_subproject=True)
    if payment_form_return and type(payment_form_return) != PaymentForm:
        return payment_form_return

    editable_payments = subproject.payments

    if type(payment_form_return) == PaymentForm:
        payment_id = payment_form_return.id.data
        editable_payments = [x for x in editable_payments if x.id != payment_form_return.id.data]

    # Populate the payment forms which allows the user to edit it
    payment_forms = {}
    if project_owner or user_in_subproject:
        payment_forms = create_payment_forms(
            subproject.payments,
            project_owner
        )

    if type(payment_form_return) == PaymentForm:
        payment_forms[payment_form_return.id.data] = payment_form_return

    # Process filled in category form
    category_form_return = process_category_form(request)
    if category_form_return:
        return category_form_return

    # Populate the category forms which allows the user to
    # edit it
    category_forms = []
    for category in Category.query.filter_by(
            subproject_id=subproject.id).order_by('name'):
        category_forms.append(
            CategoryForm(
                prefix="category_form", **{
                    'id': category.id,
                    'name': category.name,
                    'subproject_id': subproject.id,
                    'project_id': subproject.project.id
                }
            )
        )

    # Process filled in edit user form
    edit_user_form = EditUserForm(
        prefix="edit_user_form"
    )

    # Update user
    if edit_user_form.validate_on_submit():
        users = User.query.filter_by(
            id=edit_user_form.id.data
        )
        new_user_data = {}
        remove_from_subproject = False
        remove_from_subproject_id = 0
        for f in edit_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'remove_from_subproject':
                    remove_from_subproject = f.data
                elif f.short_name == 'subproject_id':
                    remove_from_subproject_id = f.data
                else:
                    new_user_data[f.short_name] = f.data

        # Update if the user exists
        if len(users.all()):
            users.update(new_user_data)
            if remove_from_subproject:
                # We need to get the user using '.first()' otherwise we
                # can't remove the project because of garbage collection
                initiatiefnemer = users.first()
                initiatiefnemer.subprojects.remove(
                    Subproject.query.get(remove_from_subproject_id)
                )

            db.session.commit()
            flash('<span class="text-default-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(
            url_for(
                'subproject',
                project_id=subproject.project.id,
                subproject_id=subproject.id
            )
        )
    else:
        util.flash_form_errors(edit_user_form, request)

    # Populate the edit user forms which allows the user to edit it
    edit_user_forms = {}
    for user in subproject.users:
        edit_user_forms[user.email] = (
            EditUserForm(
                prefix="edit_user_form", **{
                    'hidden': user.hidden,
                    'active': user.active,
                    'id': user.id,
                    'subproject_id': subproject.id
                }
            )
        )

    # Process filled in add user form
    add_user_form = AddUserForm(prefix="add_user_form")

    # Add user
    if util.validate_on_submit(add_user_form, request):
        new_user_data = {}
        for f in add_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_user_data[f.short_name] = f.data

        try:
            util.add_user(**new_user_data)
            flash(
                '<span class="text-default-green">"%s" is uitgenodigd als initiatiefnemer '
                '(of toegevoegd als initiatiefnemer als de gebruiker al '
                'bestond)' % (
                    new_user_data['email']
                )
            )
        except ValueError as e:
            flash(str(e))

        # redirect back to clear form data
        return redirect(
            url_for(
                'subproject',
                project_id=subproject.project.id,
                subproject_id=subproject.id
            )
        )
    else:
        util.flash_form_errors(add_user_form, request)

    transaction_attachment_form = ''
    edit_attachment_forms = {}
    edit_attachment_form = ''
    if project_owner or user_in_subproject:
        # Process new transaction attachment form
        transaction_attachment_form = TransactionAttachmentForm(
            prefix="transaction_attachment_form"
        )
        transaction_attachment_form_return = process_transaction_attachment_form(
            request,
            transaction_attachment_form,
            project_owner,
            user_subproject_ids,
            subproject.project.id,
            subproject.id
        )
        if transaction_attachment_form_return:
            return transaction_attachment_form_return

        # Process transaction attachment edit form
        edit_attachment_form = EditAttachmentForm(
            prefix="edit_attachment_form"
        )
        edit_attachment_form_return = process_edit_attachment_form(
            request,
            edit_attachment_form,
            subproject.project.id,
            subproject.id
        )
        if edit_attachment_form_return:
            return edit_attachment_form_return

        # Fill in attachment form data which allow a user to edit it
        attachments = []
        for payment in subproject.payments:
            attachments += payment.attachments
        edit_attachment_forms = create_edit_attachment_forms(attachments)

    # Retrieve the amounts for this subproject
    amounts = util.calculate_subproject_amounts(subproject_id)

    budget = ''
    if subproject.budget:
        budget = util.format_currency(subproject.budget)
    return render_template(
        'subproject.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER'],
        subproject=subproject,
        amounts=amounts,
        budget=budget,
        subproject_form=subproject_form,
        new_payment_form=new_payment_form,
        payment_forms=payment_forms,
        transaction_attachment_form=transaction_attachment_form,
        edit_attachment_forms=edit_attachment_forms,
        edit_user_forms=edit_user_forms,
        add_user_form=AddUserForm(prefix='add_user_form'),
        project_owner=project_owner,
        user_in_subproject=user_in_subproject,
        timestamp=util.get_export_timestamp(),
        category_forms=category_forms,
        category_form=CategoryForm(
            prefix="category_form",
            **{
                'subproject_id': subproject.id,
                'project_id': subproject.project.id
            }
        ),
        modal_id=json.dumps(modal_id),
        payment_id=json.dumps(payment_id)
    )

@app.route("/over", methods=['GET'])
def over():
    return render_template(
        'over.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER']
    )

@app.route("/meest-gestelde-vragen", methods=['GET'])
def meest_gestelde_vragen():
    return render_template(
        'meest-gestelde-vragen.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER']
    )

@app.route('/upload/<filename>')
def upload(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'], filename
    )


@app.route("/reset-wachtwoord-verzoek", methods=['GET', 'POST'])
def reset_wachtwoord_verzoek():
    form = ResetPasswordRequestForm(prefix="reset_password_request_form")
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(
            '<span class="text-default-green">Er is een e-mail verzonden met '
            'instructies om het wachtwoord te veranderen</span>'
        )
        return redirect(url_for('login'))
    return render_template(
        'reset-wachtwoord-verzoek.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER'],
        form=form
    )


@app.route("/reset-wachtwoord/<token>", methods=['GET', 'POST'])
def reset_wachtwoord(token):
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm(prefix="reset_password_request_form")
    if form.validate_on_submit():
        user.set_password(form.Wachtwoord.data)
        db.session.commit()
        flash('<span class="text-default-green">Uw wachtwoord is aangepast</span>')
        return redirect(url_for('login'))
    return render_template(
        'reset-wachtwoord.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER'],
        form=form
    )


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm(prefix="login_form")
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.Wachtwoord.data):
            flash(
                '<span class="text-default-red">Fout e-mailadres of wachtwoord</span>'
            )
            return(redirect(url_for('login')))
        login_user(user)
        return redirect(url_for('index'))
    return render_template(
        'login.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER'],
        form=form
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route("/profiel/<user_id>", methods=['GET'])
def profile(user_id):
    user = User.query.filter_by(id=user_id).first()

    return render_template(
        'profiel.html',
        user=user,
        image=File.query.filter_by(id=user.image).first(),
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER']
    )


@app.route("/profiel-bewerken", methods=['GET', 'POST'])
@login_required
def profile_edit():
    # Process filled in edit profile form
    edit_profile_form = EditProfileForm(
        prefix="edit_profile_form"
    )

    # Process image edit form (only used to remove an image)
    edit_attachment_form = EditAttachmentForm(
        prefix="edit_attachment_form"
    )
    if edit_attachment_form.remove.data:
        File.query.filter_by(id=edit_attachment_form.id.data).delete()
        db.session.commit()
        flash('<span class="text-default-green">Media is verwijderd</span>')

        # redirect back to clear form data
        return redirect(
            url_for(
                'profile',
                user_id=current_user.id
            )
        )

    # Fill in attachment form data which allows a user to edit it
    edit_attachment_forms = {}
    attachment = File.query.filter_by(id=current_user.image).first()
    if attachment:
        edit_attachment_forms = create_edit_attachment_forms([attachment])

    # Update profile
    if edit_profile_form.validate_on_submit():
        users = User.query.filter_by(
            id=current_user.id
        )
        new_profile_data = {}
        for f in edit_profile_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField' and f.short_name != 'data_file':
                new_profile_data[f.short_name] = f.data

        # Update if the user exists
        if len(users.all()):
            users.update(new_profile_data)
            db.session.commit()

            if edit_profile_form.data_file.data:
                save_attachment(edit_profile_form.data_file.data, '', users[0], 'user-image')

            flash('<span class="text-default-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(
            url_for(
                'profile',
                user_id=current_user.id
            )
        )
    else:
        util.flash_form_errors(edit_profile_form, request)

    # Populate the edit profile form which allows the user to edit it
    edit_profile_form = EditProfileForm(
        prefix="edit_profile_form", **{
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'biography': current_user.biography
        }
    )

    return render_template(
        'profiel-bewerken.html',
        use_square_borders=app.config['USE_SQUARE_BORDERS'],
        footer=app.config['FOOTER'],
        edit_profile_form=edit_profile_form,
        edit_attachment_forms=edit_attachment_forms,
        attachment=attachment
    )


@app.errorhandler(413)
def request_entity_too_large(error):
    flash(
        '<span class="text-default-red">Het verstuurde bestand is te groot. Deze mag '
        'maximaal %sMB zijn.</span>' % (
            app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024
        )
    )
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(threaded=True)
