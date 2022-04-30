import enum
import locale
from datetime import datetime
from os import urandom
from typing import Dict

from babel.numbers import format_percent
from flask import flash
from flask_login import current_user

from app import app, db
from app.email import send_invite
from app.models import Project, Subproject, User


def formatted_flash(text, color):
    return flash(f'<span class="text-default-{color}">' + text + "</span>")


def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0

    if magnitude > 0:
        return "%s%s" % (locale.format("%.1f", num), ["", "K", "M"][magnitude])
    else:
        return locale.format("%.1f", round(num))


def format_currency(num, currency_symbol="€ "):
    return "%s%s" % (
        currency_symbol,
        locale.format("%d", round(num), grouping=True, monetary=True),
    )


def calculate_amounts(model, id, payments):
    instance = model.query.get(id)

    awarded, expenses, insourcing = 0, 0, 0
    awarded += sum([x.transaction_amount for x in payments if x.route == "inkomsten"])
    # Make spent a positive number to make the output of this function consistent with
    # previous versions.
    expenses += -sum([x.transaction_amount for x in payments if x.route == "uitgaven"])
    insourcing += -sum(
        [x.transaction_amount for x in payments if x.route == "inbesteding"]
    )

    if not hasattr(
        instance, "budget"
    ):  # Hack to make this function work with debit cards.
        instance.budget = None

    if instance.budget:
        spent = expenses + insourcing
    else:
        spent = expenses

    amounts = {
        "id": id,
        "awarded": awarded,
        "awarded_str": format_currency(awarded),
        "spent": spent,
    }

    # Calculate percentage spent
    denominator = amounts["awarded"]
    if instance.budget:
        denominator = instance.budget

    if denominator == 0:
        amounts["percentage_spent_str"] = format_percent(0)
        amounts["percentage"] = 0
    else:
        amounts["percentage_spent_str"] = format_percent(amounts["spent"] / denominator)
        amounts["percentage"] = round(amounts["spent"] / denominator * 100)

    amounts["spent_str"] = format_currency(amounts["spent"])

    amounts["left_str"] = format_currency(round(amounts["awarded"] - amounts["spent"]))
    if instance.budget:
        amounts["left_str"] = format_currency(round(instance.budget - amounts["spent"]))

    return amounts


# Check if the given form is in the request
def form_in_request(form, request):
    if not request.form:
        return False

    if next(iter(request.form)).startswith(form._prefix):
        return True
    else:
        return False


# Output form errors to flashed messages
def flash_form_errors(form, request):
    # Don't print the errors if the request doesn't contain values for
    # this form
    if not request.form:
        return
    if not form_in_request(form, request):
        return

    for f in form:
        for error in f.errors:
            flash('<span class="text-default-red">%s: %s</span>' % (f.label, error))


def validate_on_submit(form, request):
    if form_in_request(form, request):
        return form.validate_on_submit()
    else:
        return False


def _set_user_role(user, admin=False, project_id=0, subproject_id=0):
    if admin:
        user.admin = True
        db.session.commit()
    if project_id:
        project = Project.query.get(project_id)
        if user in project.users:
            raise ValueError(
                "Gebruiker niet toegevoegd: deze gebruiker was al initiatiefnemer van dit initiatief"
            )
        project.users.append(user)
        db.session.commit()
    if subproject_id:
        subproject = Subproject.query.get(subproject_id)
        if user in subproject.users:
            raise ValueError(
                "Gebruiker niet toegevoegd: deze gebruiker was al activiteitnemer van deze activiteit"
            )
        subproject.users.append(user)
        db.session.commit()


def add_user(email, admin=False, project_id=0, subproject_id=0):
    # Check if a user already exists with this email address
    user = User.query.filter_by(email=email).first()

    if user:
        _set_user_role(user, admin, project_id, subproject_id)
    if not user:
        user = User(email=email)
        user.set_password(urandom(24))
        db.session.add(user)
        db.session.commit()

        _set_user_role(user, admin, project_id, subproject_id)

        # Send the new user an invitation email
        send_invite(user)


def get_export_timestamp():
    return (
        datetime.now(app.config["TZ"])
        .isoformat()[:19]
        .replace("-", "_")
        .replace("T", "-")
        .replace(":", "_")
    )


class Clearance(enum.IntEnum):
    ANONYMOUS = 1
    SUBPROJECT_OWNER = 2
    PROJECT_OWNER = 3
    FINANCIAL = 4
    ADMIN = 5


def get_permissions(clearance: Clearance) -> Dict[str, bool]:
    # TODO: construct this directly from Clearance.
    permissions = {
        "ANONYMOUS": 1,
        "SUBPROJECT_OWNER": 2,
        "PROJECT_OWNER": 3,
        "FINANCIAL": 4,
        "ADMIN": 5,
    }
    return {k: v <= clearance.value for k, v in permissions.items()}


def get_project_clearance(project: Project) -> Clearance:
    if not current_user.is_authenticated:
        return Clearance.ANONYMOUS
    elif current_user.admin:
        return Clearance.ADMIN
    elif current_user.financial:
        return Clearance.FINANCIAL
    elif project.has_user(current_user.id):
        return Clearance.PROJECT_OWNER
    elif project.contains_subprojects and any(
        [subproject.has_user(current_user.id) for subproject in project.subprojects]
    ):
        return Clearance.SUBPROJECT_OWNER
    else:
        # Default to anonymous, because that's the lowest level of clearance.
        return Clearance.ANONYMOUS


def get_subproject_clearance(subproject: Subproject) -> Clearance:
    if not current_user.is_authenticated:
        return Clearance.ANONYMOUS
    elif current_user.admin:
        return Clearance.ADMIN
    elif current_user.financial:
        return Clearance.FINANCIAL
    elif subproject.project.has_user(current_user.id):
        return Clearance.PROJECT_OWNER
    elif subproject.has_user(current_user.id):
        return Clearance.SUBPROJECT_OWNER
    else:
        # Default to anonymous, because that's the lowest level of clearance.
        return Clearance.ANONYMOUS
