from datetime import datetime
import json

from flask import (
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

import app.controllers.index as ic
import app.controllers.project as pc
import app.controllers.subproject as subpc
import app.controllers.projectprofile as ppc
import app.controllers.subprojectprofile as subppc
from app import app, db, util
from app.bng import get_bng_info, process_bng_callback
from app.email import send_password_reset_email
from app.form_processing import process_bng_link_form, process_form, BaseHandler
from app.forms import (
    AddUserForm,
    BNGLinkForm,
    EditAdminForm,
    EditAttachmentForm,
    EditProfileForm,
    EditProjectProfileForm,
    LoginForm,
    ResetPasswordForm,
    ResetPasswordRequestForm,
)

# from app.justification_report import test
from app.models import (
    BNGAccount,
    File,
    Project,
    Subproject,
    User,
    UserStory,
    save_attachment,
)
from flask_weasyprint import HTML, render_pdf, CSS
import os


# Add 'Cache-Control': 'private' header if users are logged in
@app.after_request
def after_request_callback(response):
    if current_user.is_authenticated:
        response.headers["Cache-Control"] = "private"

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
            "actief</span>"
        )
        logout_user()
        return redirect(url_for("index"))

    # If the current user has no first name, last name or biography then
    # send them to their profile page where they can add them
    if current_user.is_authenticated and request.path != "/profiel-bewerken":
        if (
            not current_user.first_name
            or not current_user.last_name
            or not current_user.biography
        ):
            flash(
                '<span class="text-default-red">Sommige velden in uw profiel zijn nog '
                "niet ingevuld. Vul deze in om verder te kunnen gaan.</span>"
            )
            return redirect(url_for("profile_user_edit"))


@app.route("/", methods=["GET", "POST"])
def index():
    modal_id = []  # This is used to pop open a modal on page load in case of
    # form errors.
    bng_info = {}

    clearance = util.get_clearance()

    # ADMIN
    edit_admin_form = EditAdminForm(prefix="edit_admin_form")
    form_redirect = process_form(BaseHandler(edit_admin_form, User))
    if form_redirect:
        return redirect(url_for("index"))

    edit_admin_forms = {}
    admins = (
        db.session.query(User)
        .filter(or_(User.admin, User.financial))
        .order_by("email")
        .all()
    )
    for admin in admins:
        edit_admin_forms[admin.email] = EditAdminForm(
            prefix="edit_admin_form", **admin.__dict__
        )

    # AddUserForm is a misleading name, because it is rendered in index.html with a flag
    # for admin = True, so users submitted here are always added as an admin.
    add_user_form = AddUserForm(prefix="add_user_form")
    if util.validate_on_submit(add_user_form, request):
        new_user_data = {}
        for f in add_user_form:
            if f.type != "SubmitField" and f.type != "CSRFTokenField":
                new_user_data[f.short_name] = f.data
        try:
            User.add_user(**new_user_data)
            util.formatted_flash(
                (
                    f"{new_user_data['email']} is uitgenodigd als admin of "
                    "initiatiefnemer. (Of zodanig toegevoegd als de "
                    "gebruiker al bestond.)"
                ),
                color="green",
            )
        except ValueError as e:
            flash(str(e))

        return redirect(url_for("index"))  # To clear form data.
    else:
        util.flash_form_errors(add_user_form, request)

    # PROJECT
    project_controller = ic.Project(clearance)
    controller_redirect = project_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    project_form = project_controller.get_forms()
    modal_id = project_controller.get_modal_ids(modal_id)

    # BNG
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

        amounts = util.calculate_amounts(
            Project, project.id, project.get_all_payments()
        )
        if project.budget:
            total_awarded += project.budget
        else:
            total_awarded += amounts["awarded"]
        total_spent += amounts["spent"]
        budget = ""
        if project.budget:
            budget = util.format_currency(project.budget)

        project_data.append(
            {
                "id": project.id,
                "name": project.name,
                "hidden": project.hidden,
                "project_owner": project_owner,
                "amounts": amounts,
                "budget": budget,
            }
        )

    if modal_id == []:
        modal_id = None

    return render_template(
        "index.html",
        background=app.config["BACKGROUND"],
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        tagline=app.config["TAGLINE"],
        footer=app.config["FOOTER"],
        project_data=project_data,
        total_awarded_str=util.human_format(total_awarded),
        total_spent_str=util.human_format(total_spent),
        project_form=project_form,
        add_user_form=AddUserForm(prefix="add_user_form"),
        edit_admin_forms=edit_admin_forms,
        user_stories=UserStory.query.all(),
        modal_id=json.dumps(modal_id),  # Does nothing if None. Loads the modal
        # on page load if supplied.
        bng_info=bng_info,
        bng_link_form=bng_link_form,
    )


@app.route("/project/<project_id>", methods=["GET", "POST"])
def project(project_id):
    modal_id = []
    payment_id = None
    bng_info = {}

    project = Project.query.get(project_id)

    clearance = util.get_clearance(project=project)

    if clearance > util.Clearance.ANONYMOUS:
        bng_info = get_bng_info(BNGAccount.query.all())

    if (not project) or (
        project.hidden and clearance < util.Clearance.SUBPROJECT_OWNER
    ):
        return render_template(
            "404.html",
            use_square_borders=app.config["USE_SQUARE_BORDERS"],
            footer=app.config["FOOTER"],
        )

    # FUNDER
    funder_controller = pc.Funder(project, clearance)
    controller_redirect = funder_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    funder_forms = funder_controller.get_forms()
    modal_id = funder_controller.get_modal_ids(modal_id)

    # SUBPROJECT
    subproject_controller = pc.Subproject(project)
    controller_redirect = subproject_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    subproject_form = subproject_controller.get_forms()
    modal_id = subproject_controller.get_modal_ids(modal_id)

    # Retrieve any subprojects a normal logged in user is part of
    user_subproject_ids = []
    if clearance >= util.Clearance.SUBPROJECT_OWNER:
        for subproject in project.subprojects:
            if subproject.has_user(current_user.id):
                user_subproject_ids.append(subproject.id)

    # PAYMENT
    payment_controller = pc.Payment(project, clearance)
    controller_redirect = payment_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    payment_forms = payment_controller.get_forms()
    modal_id = payment_controller.get_modal_ids(modal_id)
    payment_id = payment_controller.get_payment_id()

    # ATTACHMENT
    attachment_controller = pc.Attachment(project)
    controller_redirect = attachment_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    edit_attachment_forms = attachment_controller.get_forms()

    # PROJECT OWNER
    project_owner_controller = pc.ProjectOwner(project)
    controller_redirect = project_owner_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    project_owner_forms = project_owner_controller.get_forms()
    project_owner_emails = project_owner_controller.emails
    project_owners = list(zip(project_owner_forms, project_owner_emails))
    modal_id = project_owner_controller.get_modal_ids(modal_id)

    # PROJECT
    project_controller = pc.Project(project, clearance)
    controller_redirect = project_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    project_form = project_controller.get_forms()
    modal_id = project_controller.get_modal_ids(modal_id)

    # DEBIT CARD
    debit_card_controller = pc.DebitCard(project)
    controller_redirect = debit_card_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    edit_debit_card_forms = debit_card_controller.get_forms()
    edit_debit_card_numbers = debit_card_controller.debit_card_numbers
    debit_cards = list(zip(edit_debit_card_forms, edit_debit_card_numbers))
    modal_id = debit_card_controller.get_modal_ids(modal_id)
    debit_card_donuts = debit_card_controller.get_donuts()

    # CATEGORY
    category_controller = pc.Category(project)
    controller_redirect = category_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    category_forms = category_controller.get_forms()
    category_forms = list(zip(category_forms, category_controller.names))
    modal_id = category_controller.get_modal_ids(modal_id)

    # Filled with all categories for each subproject; used by some JavaScript
    # to update the categories in the select field when the user selects
    # another subproject to add the new payment to.
    categories_dict = {}
    if clearance >= util.Clearance.SUBPROJECT_OWNER:
        categories_dict = {
            x.id: x.make_category_select_options() for x in project.subprojects
        }

    payments = project.get_all_payments()
    for payment in payments:
        if payment.subproject is not None and payment.subproject.finished:
            payment.editable = False
            continue
        if clearance >= util.Clearance.PROJECT_OWNER:
            payment.editable = True
        elif clearance >= util.Clearance.SUBPROJECT_OWNER and (
            (payment.subproject and payment.subproject.has_user(current_user.id))
            or payment.subproject is None
        ):
            payment.editable = True
        else:
            payment.editable = False

    # PROJECT DATA
    amounts = util.calculate_amounts(Project, project.id, payments)

    project_data = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "hidden": project.hidden,
        "hidden_sponsors": project.hidden_sponsors,
        "amounts": amounts,
        "contains_subprojects": project.contains_subprojects,
        "category_forms": category_forms,
        "category_form": category_controller.add_form,
    }

    budget = ""
    if project.budget:
        budget = util.format_currency(project.budget)

    if len(modal_id) == 0:
        modal_id = None

    return render_template(
        "project.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        project=project,
        project_data=project_data,
        amounts=amounts,
        budget=budget,
        payments=payments,
        project_form=project_form,
        project_owners=project_owners,
        add_user_form=project_owner_controller.add_form,
        add_debit_card_form=debit_card_controller.add_form,
        subproject_form=subproject_form,
        new_payment_form=payment_controller.add_payment_form,
        new_topup_form=payment_controller.add_topup_form,
        categories_dict=categories_dict,
        payment_forms=payment_forms,
        transaction_attachment_form=attachment_controller.add_form,
        edit_attachment_forms=edit_attachment_forms,
        funder_forms=funder_forms,
        new_funder_form=funder_controller.add_form,
        permissions=util.get_permissions(clearance),
        timestamp=util.get_export_timestamp(),
        modal_id=json.dumps(modal_id),
        payment_id=json.dumps(payment_id),
        bng_info=bng_info,
        edit_debit_card_forms=debit_cards,
        debit_card_donuts=debit_card_donuts,
        user_subproject_ids=user_subproject_ids,
    )


@app.route("/project/<project_id>/subproject/<subproject_id>", methods=["GET", "POST"])
def subproject(project_id, subproject_id):
    modal_id = []
    payment_id = None

    subproject = Subproject.query.get(subproject_id)

    clearance = util.get_clearance(subproject=subproject)

    if (not subproject) or (
        subproject.hidden and clearance < util.Clearance.SUBPROJECT_OWNER
    ):
        return render_template(
            "404.html",
            use_square_borders=app.config["USE_SQUARE_BORDERS"],
            footer=app.config["FOOTER"],
        )

    # FUNDER
    funder_controller = subpc.Funder(subproject, clearance)
    redirect = funder_controller.process_forms()
    if redirect:
        return redirect
    funder_forms = funder_controller.get_forms()
    modal_id = funder_controller.get_modal_ids(modal_id)

    # SUBPROJECT
    subproject_controller = subpc.Subproject(subproject)
    redirect = subproject_controller.process_forms()
    if redirect:
        return redirect
    subproject_form = subproject_controller.get_forms()
    modal_id = subproject_controller.get_modal_ids(modal_id)

    # PAYMENT
    payment_controller = subpc.Payment(subproject, clearance)
    controller_redirect = payment_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    payment_forms = payment_controller.get_forms()
    modal_id = payment_controller.get_modal_ids(modal_id)
    payment_id = payment_controller.get_payment_id()

    # ATTACHMENT
    attachment_controller = subpc.Attachment(subproject)
    controller_redirect = attachment_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    edit_attachment_forms = attachment_controller.get_forms()

    # CATEGORY
    category_controller = subpc.Category(subproject)
    controller_redirect = category_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    category_forms = category_controller.get_forms()
    category_forms = list(zip(category_forms, category_controller.names))
    modal_id = category_controller.get_modal_ids(modal_id)

    # SUBPROJECT OWNER
    subproject_owner_controller = subpc.SubprojectOwner(subproject)
    controller_redirect = subproject_owner_controller.process_forms()
    if controller_redirect:
        return controller_redirect
    subproject_owner_forms = subproject_owner_controller.get_forms()
    subproject_owner_emails = subproject_owner_controller.emails
    subproject_owners = list(zip(subproject_owner_forms, subproject_owner_emails))
    modal_id = subproject_owner_controller.get_modal_ids(modal_id)

    payments = subproject.payments.all()
    for payment in payments:
        if subproject.finished:
            payment.editable = False
            continue
        if clearance >= util.Clearance.PROJECT_OWNER:
            payment.editable = True
        elif clearance >= util.Clearance.SUBPROJECT_OWNER:
            payment.editable = True
        else:
            payment.editable = False

    amounts = util.calculate_amounts(
        Subproject,
        subproject_id,
        subproject.payments.all(),
    )

    budget = ""
    if subproject.budget:
        budget = util.format_currency(subproject.budget)

    if len(modal_id) == 0:
        modal_id = None

    return render_template(
        "subproject.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        subproject=subproject,
        amounts=amounts,
        payments=payments,
        budget=budget,
        subproject_form=subproject_form,
        payment_forms=payment_forms,
        new_payment_form=payment_controller.add_payment_form,
        transaction_attachment_form=attachment_controller.add_form,
        edit_attachment_forms=edit_attachment_forms,
        subproject_owners=subproject_owners,
        add_user_form=subproject_owner_controller.add_form,
        permissions=util.get_permissions(clearance),
        timestamp=util.get_export_timestamp(),
        category_forms=category_forms,
        category_form=category_controller.add_form,
        modal_id=json.dumps(modal_id),
        payment_id=json.dumps(payment_id),
        funder_forms=funder_forms,
        add_funder_form=funder_controller.add_form,
        funder_info=funder_controller.funder_info,
    )


@app.route("/over", methods=["GET"])
def over():
    return render_template(
        "over.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
    )


@app.route("/meest-gestelde-vragen", methods=["GET"])
def meest_gestelde_vragen():
    return render_template(
        "meest-gestelde-vragen.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
    )


@app.route("/upload/<filename>")
def upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/reset-wachtwoord-verzoek", methods=["GET", "POST"])
def reset_wachtwoord_verzoek():
    form = ResetPasswordRequestForm(prefix="reset_password_request_form")
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(
            '<span class="text-default-green">Er is een e-mail verzonden met '
            "instructies om het wachtwoord te veranderen</span>"
        )
        return redirect(url_for("login"))
    return render_template(
        "reset-wachtwoord-verzoek.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        form=form,
    )


@app.route("/reset-wachtwoord/<token>", methods=["GET", "POST"])
def reset_wachtwoord(token):
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for("index"))
    form = ResetPasswordForm(prefix="reset_password_request_form")
    if form.validate_on_submit():
        user.set_password(form.Wachtwoord.data)
        db.session.commit()
        flash('<span class="text-default-green">Uw wachtwoord is aangepast</span>')
        return redirect(url_for("login"))
    return render_template(
        "reset-wachtwoord.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        form=form,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm(prefix="login_form")
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.Wachtwoord.data):
            flash(
                '<span class="text-default-red">Fout e-mailadres of wachtwoord</span>'
            )
            return redirect(url_for("login"))
        login_user(user)
        return redirect(url_for("index"))
    return render_template(
        "login.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        form=form,
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/profiel/gebruiker/<user_id>", methods=["GET"])
def profile_user(user_id):
    user = User.query.filter_by(id=user_id).first()

    return render_template(
        "profile/user.html",
        user=user,
        image=File.query.filter_by(id=user.image).first(),
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
    )


@app.route("/profiel/project/<project_id>", methods=["GET", "POST"])
def profile_project(project_id):

    modal_id = []

    project = Project.query.filter_by(id=project_id).first()

    clearance = util.get_clearance(project=project)

    if not project:
        return render_template(
            "404.html",
            use_square_borders=app.config["USE_SQUARE_BORDERS"],
            footer=app.config["FOOTER"],
        )

    # TODO: Permissions

    edit_attachment_form = EditAttachmentForm(prefix="edit_attachment_form")
    if edit_attachment_form.remove.data:
        File.query.filter_by(id=edit_attachment_form.id.data).delete()
        db.session.commit()
        util.formatted_flash("Media is verwijderd.", color="green")
        return redirect(url_for("profile_project", project_id=project.id))

    image = File.query.filter_by(id=project.image).first()
    if image is not None:
        edit_attachment_form = EditAttachmentForm(
            **image.__dict__, prefix="edit_attachment_form"
        )

    edit_project_profile_form = EditProjectProfileForm(prefix="edit_profile_form")
    if (
        util.validate_on_submit(edit_project_profile_form, request)
        and edit_project_profile_form.data_file.data
    ):
        save_attachment(
            edit_project_profile_form.data_file.data, "", project, "project-attachment"
        )
        util.formatted_flash("Media is toegevoegd.", color="green")
        return redirect(url_for("profile_project", project_id=project.id))

    controller = ppc.JustifyProjectController(project)
    controller_redirect = controller.process_forms()
    if controller_redirect:
        return controller_redirect
    justify_project_form = controller.get_forms()
    concept_justify_project_form = controller.get_concept_justify_form()
    modal_id = controller.get_modal_ids(modal_id)

    if len(modal_id) == 0:
        modal_id = None

    return render_template(
        "profile/project.html",
        project=project,
        image=image,
        edit_attachment_form=edit_attachment_form,
        edit_project_profile_form=edit_project_profile_form,
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        total_funder_budget=util.format_currency(
            sum([x.budget for x in project.funders])
        ),
        justify_project_form=justify_project_form,
        concept_justify_project_form=concept_justify_project_form,
        funder_info=controller.funder_info,
        modal_id=modal_id,
        permissions=util.get_permissions(clearance),
    )


@app.route("/report/project/<project_id>", methods=["GET"])
def justification_report(project_id):
    project = Project.query.get(project_id)

    # TODO: Refactor this in combination with save_attachment.
    thumbnail_paths = [
        os.path.splitext(attachment.filename)[0] + "_thumb.jpeg"
        for attachment in project.get_all_attachments()
        if attachment.mimetype in ["image/jpeg", "image/jpg", "image/png"]
    ]

    date_of_issue = datetime.now().strftime("%d-%m-%Y")

    rendered_template = render_template(
        "justification-rapport.html",
        project=project,
        thumbnail_paths=thumbnail_paths,
        date_of_issue=date_of_issue,
    )
    base_url = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    x = HTML(
        string=rendered_template,
        base_url=base_url,
    )
    y = CSS(
        filename="./app/static/dist/styles/justification_report.css", base_url=base_url
    )
    return render_pdf(x, stylesheets=[y])


@app.route("/profiel/subproject/<subproject_id>", methods=["GET", "POST"])
def profile_subproject(subproject_id):
    modal_id = []

    subproject = Subproject.query.filter_by(id=subproject_id).first()

    clearance = util.get_clearance(subproject=subproject)

    if not subproject:
        return render_template(
            "404.html",
            use_square_borders=app.config["USE_SQUARE_BORDERS"],
            footer=app.config["FOOTER"],
        )

    # TODO: Permissions

    edit_attachment_form = EditAttachmentForm(prefix="edit_attachment_form")
    if edit_attachment_form.remove.data:
        File.query.filter_by(id=edit_attachment_form.id.data).delete()
        db.session.commit()
        util.formatted_flash("Media is verwijderd.", color="green")
        return redirect(url_for("profile_subproject", subproject_id=subproject.id))

    image = File.query.filter_by(id=subproject.image).first()
    if image is not None:
        edit_attachment_form = EditAttachmentForm(
            **image.__dict__, prefix="edit_attachment_form"
        )

    edit_project_profile_form = EditProjectProfileForm(prefix="edit_profile_form")
    if (
        util.validate_on_submit(edit_project_profile_form, request)
        and edit_project_profile_form.data_file.data
    ):
        save_attachment(
            edit_project_profile_form.data_file.data,
            "",
            subproject,
            "subproject-attachment",
        )
        util.formatted_flash("Media is toegevoegd.", color="green")
        return redirect(url_for("profile_subproject", subproject_id=subproject.id))

    controller = subppc.FinishSubprojectController(subproject)
    controller_redirect = controller.process_forms()
    if controller_redirect:
        return controller_redirect
    finish_subproject_form = controller.get_forms()
    modal_id = controller.get_modal_ids(modal_id)

    financial_info = subproject.financial_summary

    if len(modal_id) == 0:
        modal_id = None

    return render_template(
        "profile/subproject.html",
        subproject=subproject,
        image=image,
        edit_attachment_form=edit_attachment_form,
        edit_project_profile_form=edit_project_profile_form,
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        total_funder_budget=util.format_currency(
            sum([x.budget for x in subproject.funders])
        ),
        finish_subproject_form=finish_subproject_form,
        undo_finish_subproject_form=controller.undo_form,
        modal_id=modal_id,
        funders=controller.funders,
        financial_info=financial_info,
        permissions=util.get_permissions(clearance),
    )


@app.route("/profiel-bewerken", methods=["GET", "POST"])
@login_required
def profile_user_edit():
    edit_profile_form = EditProfileForm(prefix="edit_profile_form")

    edit_attachment_form = EditAttachmentForm(prefix="edit_attachment_form")
    if edit_attachment_form.remove.data:
        File.query.filter_by(id=edit_attachment_form.id.data).delete()
        db.session.commit()
        flash('<span class="text-default-green">Media is verwijderd</span>')

        return redirect(url_for("profile_user", user_id=current_user.id))

    edit_attachment_forms = {}
    attachment = File.query.filter_by(id=current_user.image).first()
    if attachment:
        edit_attachment_forms[attachment.id] = EditAttachmentForm(
            **attachment.__dict__, prefix="edit_attachment_form"
        )

    if edit_profile_form.validate_on_submit():
        users = User.query.filter_by(id=current_user.id)
        new_profile_data = {}
        for f in edit_profile_form:
            if (
                f.type != "SubmitField"
                and f.type != "CSRFTokenField"
                and f.short_name != "data_file"
            ):
                new_profile_data[f.short_name] = f.data

        if len(users.all()):
            users.update(new_profile_data)
            db.session.commit()

            if edit_profile_form.data_file.data:
                save_attachment(
                    edit_profile_form.data_file.data, "", users[0], "user-image"
                )

            flash('<span class="text-default-green">gebruiker is bijgewerkt</span>')

        return redirect(url_for("profile_user", user_id=current_user.id))
    else:
        util.flash_form_errors(edit_profile_form, request)

    edit_profile_form = EditProfileForm(
        prefix="edit_profile_form",
        **{
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "biography": current_user.biography,
        },
    )

    return render_template(
        "profiel-bewerken.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
        edit_profile_form=edit_profile_form,
        edit_attachment_forms=edit_attachment_forms,
        attachment=attachment,
    )


@app.errorhandler(413)
def request_entity_too_large(error):
    flash(
        '<span class="text-default-red">Het verstuurde bestand is te groot. Deze mag '
        "maximaal %sMB zijn.</span>" % (app.config["MAX_CONTENT_LENGTH"] / 1024 / 1024)
    )
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(threaded=True)
