from flask import (
    render_template, redirect, url_for, flash, request,
    send_from_directory
)
from flask_login import login_required, login_user, logout_user, current_user
from wtforms.validators import ValidationError

from app import app, db
from app.forms import (
    DebitCardForm, ResetPasswordRequestForm, ResetPasswordForm, LoginForm, NewProjectForm,
    EditProjectForm, SubprojectForm, TransactionAttachmentForm,
    EditAttachmentForm, FunderForm, AddUserForm, EditAdminForm,
    EditProjectOwnerForm, EditUserForm, EditProfileForm, CategoryForm,
    NewPaymentForm, PaymentForm, BNGLinkForm
)
from app.email import send_password_reset_email
from app.models import (
    User, Project, Subproject, Payment, UserStory, IBAN, File, Funder, Category, BNGAccount, DebitCard, payment_attachment
)
from app.form_processing import (
    generate_new_payment_form, process_category_form, process_form, process_new_payment_form, process_payment_form, create_payment_forms,
    process_transaction_attachment_form, create_edit_attachment_forms,
    process_edit_attachment_form, save_attachment,
    process_bng_link_form, process_bng_callback, get_bng_info, get_bng_payments, process_new_project_form
)
from sqlalchemy.exc import IntegrityError

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
    modal_id = None  # This is used to pop open a modal on page load in case of
    # form errors.
    bng_info = {}

    # ADMIN
    # --------------------------------------------------------------------------------
    edit_admin_form = EditAdminForm(prefix="edit_admin_form")
    form_redirect = process_form(edit_admin_form, User)
    if form_redirect:
        return form_redirect

    edit_admin_forms = {}
    for admin in User.query.filter_by(admin=True).order_by('email'):
        edit_admin_forms[admin.email] = EditAdminForm(
            prefix="edit_admin_form", **{
                'admin': admin.admin,
                'active': admin.active,
                'id': admin.id
            }
        )

    # AddUserForm is a misleading name, because it is rendered in index.html with a flag
    # for admin = True, so users submitted here are always added as an admin.
    add_user_form = AddUserForm(prefix="add_user_form")
    if util.validate_on_submit(add_user_form, request):
        new_user_data = {}
        for f in add_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_user_data[f.short_name] = f.data

        try:
            util.add_user(**new_user_data)
            util.formatted_flash((
                f"{new_user_data['email']} is uitgenodigd als admin of project owner. "
                "(Of zodanig toegevoegd als de gebruiker al bestond.)"), color="green"
            )
        except ValueError as e:
            flash(str(e))

        return redirect(url_for('index'))  # To clear form data.
    else:
        util.flash_form_errors(add_user_form, request)

    # PROJECT
    # --------------------------------------------------------------------------------
    project_form = NewProjectForm(prefix="project_form")
    form_redirect = process_new_project_form(project_form)
    if form_redirect:
        return form_redirect
    if len(project_form.errors) > 0:
        modal_id = ["#modal-project-toevoegen"]

    # BNG
    # --------------------------------------------------------------------------------
    if current_user.is_authenticated:
        if current_user.admin:
            bng_info = get_bng_info(BNGAccount.query.all())

    if request.args.get("state"):
        bng_redirect = process_bng_callback(request)
        if bng_redirect:
            return bng_redirect

    bng_link_form = BNGLinkForm(prefix="bng_link_form")
    form_redirect = process_bng_link_form(bng_link_form)
    if form_redirect:
        return form_redirect
    if len(bng_link_form.errors) > 0:
        modal_id = ["#modal-bng-koppeling-beheren"]

    # PROJECT DATA
    # --------------------------------------------------------------------------------
    total_awarded = 0
    total_spent = 0
    project_data = []
    for project in Project.query.all():
        project_owner = False
        if current_user.is_authenticated and (
            current_user.admin or project.has_user(current_user.id)
        ):
            project_owner = True

        if project.hidden and not project_owner:
            continue

        amounts = util.calculate_project_amounts(project.id)
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
        modal_id=json.dumps(modal_id),  # Does nothing if None. Loads the modal
        # on page load if supplied.
        bng_info=bng_info,
        bng_link_form=bng_link_form
    )


@app.route("/project/<project_id>", methods=['GET', 'POST'])
def project(project_id):
    modal_id = None  # This is used to pop open a modal on page load in case of
    # form errors.
    payment_id = None  # This is used to pop open the right detail view of a
    # payment in the bootstrap table of payments in case of form errors.
    bng_info = {}

    if current_user.is_authenticated:
        bng_info = get_bng_info(BNGAccount.query.all())

    project = Project.query.get(project_id)

    if not project:
        return render_template(
            '404.html',
            use_square_borders=app.config['USE_SQUARE_BORDERS'],
            footer=app.config['FOOTER']
        )

    # A project owner is either an admin or a user that is part of this
    # project
    is_project_owner = False
    if current_user.is_authenticated and (
        current_user.admin or project.has_user(current_user.id)
    ):
        is_project_owner = True

    if project.hidden and not is_project_owner:
        return render_template(
            '404.html',
            use_square_borders=app.config['USE_SQUARE_BORDERS'],
            footer=app.config['FOOTER']
        )

    # FUNDER
    # --------------------------------------------------------------------------------
    funder_form = FunderForm(prefix="funder_form")
    funder_form.project_id.data = project.id
    form_redirect = process_form(funder_form, Funder)
    if form_redirect:
        return form_redirect

    funder_forms = []
    for funder in project.funders:
        funder_forms.append(
            FunderForm(prefix="funder_form", **{
                'name': funder.name,
                'url': funder.url,
                'id': funder.id
            })
        )

    # SUBPROJECT
    # --------------------------------------------------------------------------------
    subproject_form = SubprojectForm(prefix="subproject_form")
    form_redirect = process_form(subproject_form, Subproject)
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
    if project.contains_subprojects and current_user.is_authenticated and not is_project_owner:
        for subproject in project.subprojects:
            if subproject.has_user(current_user.id):
                user_subproject_ids.append(subproject.id)

    # PAYMENT AND ATTACHMENT
    # --------------------------------------------------------------------------------
    new_payment_form = ''
    # Filled with all categories for each subproject; used by some JavaScript
    # to update the categories in the select field when the user selects
    # another subproject to add the new payment to.
    categories_dict = {}
    if is_project_owner:
        categories_dict = {x.id: x.make_category_select_options()
                           for x in project.subprojects}

        new_payment_form = generate_new_payment_form(project, subproject=None)
        form_redirect = process_new_payment_form(new_payment_form, project, subproject=None)
        if form_redirect:
            return form_redirect
        if len(new_payment_form.errors) > 0:
            modal_id = ["#modal-transactie-toevoegen"]

    payment_forms = {}
    transaction_attachment_form = ''
    edit_attachment_forms = {}
    edit_attachment_form = ''
    if is_project_owner or user_subproject_ids:
        payment_form_return = process_payment_form(request, project, is_project_owner, user_subproject_ids, is_subproject=False)
        if payment_form_return and type(payment_form_return) != PaymentForm:
            return payment_form_return

        if is_project_owner:
            editable_payments = (
                db.session.query(Payment).
                join(DebitCard).
                join(Project).
                filter(Project.id == project.id).
                all()
            )
            editable_attachments = (
                db.session.query(File).
                join(payment_attachment).
                join(Payment).
                filter(Payment.id.in_([x.id for x in editable_payments])).
                all()
            )
        elif user_subproject_ids:
            # Payments are now always assigned manually to subprojects.
            # A user that is not project owner or admin is only allowed to edit payments from its subprojects.
            raise NotImplementedError("Not implemented yet.")

        if type(payment_form_return) == PaymentForm:
            payment_id = payment_form_return.id.data
            editable_payments = [x for x in editable_payments if x.id != payment_form_return.id.data]

        payment_forms = create_payment_forms(editable_payments)

        if type(payment_form_return) == PaymentForm:
            payment_forms[payment_form_return.id.data] = payment_form_return

        transaction_attachment_form = TransactionAttachmentForm(
            prefix="transaction_attachment_form"
        )
        transaction_attachment_form_return = process_transaction_attachment_form(
            request,
            transaction_attachment_form,
            is_project_owner,
            user_subproject_ids,
            project.id
        )
        if transaction_attachment_form_return:
            return transaction_attachment_form_return

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

        edit_attachment_forms = create_edit_attachment_forms(editable_attachments)

    # TODO: Add manual payments that are not linked to a debit card.
    payments = db.session.query(Payment).join(DebitCard).join(Project).filter(Project.id == project.id).all()

    # PROJECT OWNER
    # TODO: This really should be refactored to use process_form.
    # --------------------------------------------------------------------------------
    edit_project_owner_form = EditProjectOwnerForm(
        prefix="edit_project_owner_form"
    )

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

        return redirect(url_for('project', project_id=project.id))
    else:
        if len(edit_project_owner_form.errors) > 0:
            modal_id = ["#project-bewerken", "#project-owner-toevoegen"]

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

    add_user_form = AddUserForm(prefix="add_user_form")

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

        return redirect(url_for('project', project_id=project.id))
    else:
        if len(add_user_form.errors) > 0:
            modal_id = ["#project-bewerken", "#project-owner-toevoegen"]

    # PROJECT
    # Notice how it's not allowed to change contains_subprojects after creation.
    # --------------------------------------------------------------------------------
    project_form = EditProjectForm(prefix="project_form")
    project_form.contains_subprojects.data = project.contains_subprojects
    form_redirect = process_form(project_form, Project)
    if form_redirect:
        return form_redirect
    if len(project_form.errors) > 0:
        modal_id = ["#project-bewerken"]

    if not util.form_in_request(project_form, request):
        project_form = EditProjectForm(prefix="project_form", **{
            'name': project.name,
            'description': project.description,
            'hidden': project.hidden,
            'hidden_sponsors': project.hidden_sponsors,
            'budget': project.budget,
            'id': project.id,
            'contains_subprojects': project.contains_subprojects
        })
    project_form.contains_subprojects.render_kw = {'disabled': ''}

    # DEBIT CARD
    # --------------------------------------------------------------------------------
    add_debit_card_form = DebitCardForm()
    form_redirect = process_form(add_debit_card_form, DebitCard)
    if form_redirect:
        return form_redirect
    add_debit_card_form.project_id.data = project.id

    edit_debit_card_forms = {}
    for debit_card in DebitCard.query.filter_by(project_id=project.id):
        edit_debit_card_forms[debit_card.card_number] = DebitCardForm(**{
            "id": debit_card.id,
            "card_number": debit_card.card_number,
            "project_id": debit_card.project_id})

    # CATEGORY
    # --------------------------------------------------------------------------------
    category_form_return = process_category_form(request)
    if category_form_return:
        return category_form_return

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

    # PROJECT DATA
    # --------------------------------------------------------------------------------
    amounts = util.calculate_project_amounts(project.id)

    project_data = {
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'hidden': project.hidden,
        'hidden_sponsors': project.hidden_sponsors,
        'amounts': amounts,
        'contains_subprojects': project.contains_subprojects,
        'category_forms': category_forms,
        'category_form': CategoryForm(prefix="category_form", **{'project_id': project.id})
    }

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
        add_debit_card_form=add_debit_card_form,
        subproject_form=subproject_form,
        new_payment_form=new_payment_form,
        categories_dict=categories_dict,
        payment_forms=payment_forms,
        transaction_attachment_form=transaction_attachment_form,
        edit_attachment_forms=edit_attachment_forms,
        funder_forms=funder_forms,
        new_funder_form=funder_form,
        project_owner=is_project_owner,  # TODO: Always use "is_project_owner" instead of "project_owner"
        user_subproject_ids=user_subproject_ids,
        timestamp=util.get_export_timestamp(),
        modal_id=json.dumps(modal_id),
        payment_id=json.dumps(payment_id),
        bng_info=bng_info,
        edit_debit_card_forms=edit_debit_card_forms
    )


@app.route(
    "/project/<project_id>/subproject/<subproject_id>", methods=['GET', 'POST']
)
def subproject(project_id, subproject_id):
    modal_id = None  # This is used to pop open a modal on page load in case of
    # form errors.
    payment_id = None  # This is used to pop open the right detail view of a
    # payment in the bootstrap table of payments in case of form errors.

    subproject = Subproject.query.get(subproject_id)

    if not subproject:
        return render_template(
            '404.html',
            use_square_borders=app.config['USE_SQUARE_BORDERS'],
            footer=app.config['FOOTER']
        )

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

    # SUBPROJECT
    # --------------------------------------------------------------------------------
    subproject_form = SubprojectForm(prefix="subproject_form")
    form_redirect = process_form(subproject_form, Subproject)
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

    # PAYMENT AND ATTACHMENT
    # --------------------------------------------------------------------------------
    new_payment_form = ''
    if project_owner:
        new_payment_form = generate_new_payment_form(project=None, subproject=subproject)
        form_redirect = process_new_payment_form(new_payment_form, project=None, subproject=subproject)
        if form_redirect:
            return form_redirect
        if len(new_payment_form.errors) > 0:
            modal_id = ["#transactie-toevoegen"]

    payment_form_return = process_payment_form(request, subproject, project_owner, user_subproject_ids, is_subproject=True)
    if payment_form_return and type(payment_form_return) != PaymentForm:
        return payment_form_return

    editable_payments = subproject.payments

    if type(payment_form_return) == PaymentForm:
        payment_id = payment_form_return.id.data
        editable_payments = [x for x in editable_payments if x.id != payment_form_return.id.data]

    payment_forms = {}
    if project_owner or user_in_subproject:
        payment_forms = create_payment_forms(subproject.payments)

    if type(payment_form_return) == PaymentForm:
        payment_forms[payment_form_return.id.data] = payment_form_return

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

    # CATEGORY
    # --------------------------------------------------------------------------------
    category_form_return = process_category_form(request)
    if category_form_return:
        return category_form_return

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

    # SUBPROJECT OWNER
    # TODO: This really should be refactored to use process_form.
    # --------------------------------------------------------------------------------
    edit_user_form = EditUserForm(
        prefix="edit_user_form"
    )

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

    add_user_form = AddUserForm(prefix="add_user_form")

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
