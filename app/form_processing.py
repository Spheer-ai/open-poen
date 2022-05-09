from enum import Enum
from time import time
from typing import Callable, Dict, Optional, Union

import jwt
from flask import redirect, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from requests import ConnectionError
from sqlalchemy.exc import IntegrityError

from app import app
from app import bng as bng
from app import db, util
from app.models import BNGAccount
from app.util import formatted_flash


def filter_fields(form: FlaskForm) -> Dict:
    # Filter out these field names, because they are never saved in the DB.
    fields = {
        x.short_name: x.data
        for x in form
        if x.type not in ["SubmitField", "CSRFTokenField"]
    }
    # Set empty strings to None to keep everything consistent. Also because column like
    # foreign keys can't handle empty strings.
    for key, value in fields.items():
        # In case of FieldLists. Extra check so that we skip data from QuerySelectMultipleField.
        if type(value) == list and not any([isinstance(i, db.Model) for i in value]):
            fields[key] = [
                {k: (v if v != "" else None) for k, v in x.items()} for x in value
            ]
        # In case of single fields.
        else:
            fields[key] = value if value != "" else None
    return fields


def return_redirect(project_id: int, subproject_id: Union[None, int]):
    # Redirect back to clear form data
    if subproject_id:
        return redirect(
            url_for("subproject", project_id=project_id, subproject_id=subproject_id)
        )

    return redirect(url_for("project", project_id=project_id))


def process_bng_link_form(form):
    if not current_user.is_authenticated or not current_user.admin:
        return None

    if form.remove.data:
        bng_account = BNGAccount.query.filter_by(user_id=current_user.id).all()
        if len(bng_account) > 1:
            raise NotImplementedError(
                "A user should not be able to have more than one BNG account."
            )
        if len(bng_account) == 0:
            formatted_flash(
                (
                    "De BNG-koppeling is niet verwijderd. Alleen degene die de koppeling heeft aangemaakt, "
                    "mag deze verwijderen."
                ),
                color="red",
            )
            return
        bng_account = bng_account[0]

        # TODO: This returns a 401 now for the Sandbox, but I don't see how there is
        # anything wrong with my request.
        bng.delete_consent(bng_account.consent_id, bng_account.access_token)

        db.session.delete(bng_account)
        db.session.commit()
        formatted_flash("De BNG-koppeling is verwijderd.", color="green")
        return redirect(url_for("index"))

    if not util.validate_on_submit(form, request):
        return

    if form.iban.data in [x.iban for x in BNGAccount.query.all()]:
        formatted_flash(
            (
                "Het aanmaken van de BNG-koppeling is mislukt. Er bestaat al een koppeling met"
                f"deze IBAN: {form.iban.data}."
            ),
            color="red",
        )
        return

    try:
        consent_id, oauth_url = bng.create_consent(
            iban=form.iban.data, valid_until=form.valid_until.data
        )
    except ConnectionError as e:
        app.logger.error(repr(e))
        formatted_flash(
            (
                "Het aanmaken van de BNG-koppeling is mislukt door een verbindingsfout. De beheerder van Open "
                "Poen is op de hoogte gesteld. Probeer het later nog eens, of neem contact op met de "
                "beheerder."
            ),
            color="red",
        )
        return

    bng_token = jwt.encode(
        {
            "user_id": current_user.id,
            "iban": form.iban.data,
            "bank_name": "BNG",
            "exp": time() + 1800,
            "consent_id": consent_id,
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    ).decode("utf-8")

    return redirect(oauth_url.format(bng_token))


class Status(Enum):
    succesful_delete = 1
    succesful_edit = 2
    failed_edit = 3
    succesful_create = 4
    failed_create = 5
    not_found = 6


def process_form(
    form: FlaskForm,
    object,
    alt_update: Optional[Callable] = None,
    alt_create: Optional[Callable] = None,
) -> Union[None, Status]:
    # TODO: Type hint for object argument.
    if hasattr(form, "remove") and form.remove.data:
        instance = object.query.get(form.id.data)
        if instance is None:
            return Status.not_found
        db.session.delete(instance)
        db.session.commit()
        util.formatted_flash(instance.message_after_delete, color="green")
        return Status.succesful_delete

    if not util.validate_on_submit(form, request):
        return None

    # TODO: Make filter_fields work for nested dicts.
    # TODO: Deal with Model instances in case of QueryMultipleSelectField.
    data = filter_fields(form)

    if hasattr(form, "id") and form.id.data is not None:
        instance = object.query.get(data["id"])
        if not instance:
            util.formatted_flash(
                "Aanpassen mislukt. Dit object bestaat niet.", color="red"
            )
            return Status.not_found
        try:
            if alt_update is not None:
                alt_update(instance, **data)  # Executes an instance method.
            else:
                instance.update(data)
            util.formatted_flash(instance.message_after_edit, color="green")
            return Status.succesful_edit
        except (ValueError, IntegrityError) as e:
            app.logger.error(repr(e))
            db.session().rollback()
            util.formatted_flash(
                instance.message_after_edit_error(e, data), color="red"
            )
            return Status.failed_edit
    else:
        try:
            if alt_create is not None:
                instance = alt_create(**data)  # Executes a class method.
            else:
                instance = object.create(data)
            util.formatted_flash(instance.message_after_create, color="green")
            return Status.succesful_create
        except (ValueError, IntegrityError) as e:
            app.logger.error(repr(e))
            db.session().rollback()
            util.formatted_flash(
                object.message_after_create_error(e, data), color="red"
            )
            return Status.failed_create
