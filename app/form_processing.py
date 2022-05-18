from enum import Enum
from time import time
from typing import Callable, Dict, Optional, Union

import jwt
from flask import redirect, request, url_for, Response
from flask_login import current_user
from flask_wtf import FlaskForm
from requests import ConnectionError
from sqlalchemy.exc import IntegrityError

from app import app
from app import bng as bng
from app import db, util
from app.models import BNGAccount
from app.util import formatted_flash, form_in_request
from app.better_utils import format_flash
from flask import flash
from app.exceptions import known_exceptions


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
        # In case of FieldLists. Extra check so that we skip data from
        # QuerySelectMultipleField.
        if type(value) == list and not any([isinstance(i, db.Model) for i in value]):
            fields[key] = [
                {k: (v if v != "" else None) for k, v in x.items()} for x in value
            ]
        # In case of single fields.
        else:
            fields[key] = value if value != "" else None
    return fields


def return_redirect(project_id: int, subproject_id: Union[None, int]):
    if subproject_id:
        return redirect(
            url_for("subproject", project_id=project_id, subproject_id=subproject_id)
        )

    return redirect(url_for("project", project_id=project_id))


def process_bng_link_form(form: FlaskForm) -> Union[None, Response]:
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
                    "De BNG-koppeling is niet verwijderd. Alleen degene die de "
                    "koppeling heeft aangemaakt, mag deze verwijderen."
                ),
                color="red",
            )
            return None
        bng_account = bng_account[0]

        # TODO: This returns a 401 now for the Sandbox, but I don't see how there is
        # anything wrong with my request.
        bng.delete_consent(bng_account.consent_id, bng_account.access_token)

        db.session.delete(bng_account)
        db.session.commit()
        formatted_flash("De BNG-koppeling is verwijderd.", color="green")
        return redirect(url_for("index"))

    if not util.validate_on_submit(form, request):
        return None

    if form.iban.data in [x.iban for x in BNGAccount.query.all()]:
        formatted_flash(
            (
                "Het aanmaken van de BNG-koppeling is mislukt. Er bestaat al "
                f"een koppeling met deze IBAN: {form.iban.data}."
            ),
            color="red",
        )
        return None

    try:
        consent_id, oauth_url = bng.create_consent(
            iban=form.iban.data, valid_until=form.valid_until.data
        )
    except ConnectionError as e:
        app.logger.error(repr(e))
        formatted_flash(
            (
                "Het aanmaken van de BNG-koppeling is mislukt door een "
                "verbindingsfout. De beheerder van Open Poen is op de hoogte gesteld. "
                "Probeer het later nog eens, of neem contact op met de beheerder."
            ),
            color="red",
        )
        return None

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
    if not form_in_request(form, request):
        return None

    app.logger.info(f"Form {str(form)} for object {str(object)} is submitted.")

    if hasattr(form, "remove") and form.remove.data:
        instance = object.query.get(form.id.data)
        if instance is None:
            return Status.not_found
        db.session.delete(instance)
        db.session.commit()
        flash(instance.on_succesful_delete)
        return Status.succesful_delete

    if not form.validate_on_submit():
        app.logger.info(f"Form is invalid. Data: {form.data}. Errors: {form.errors}.")
        return None

    app.logger.info(f"Form is valid. Data: {form.data}.")

    data = filter_fields(form)

    if hasattr(form, "id") and form.id.data is not None:
        app.logger.info("Form is used to edit an existing entity.")
        instance = object.query.get(data["id"])
        if not instance:
            return Status.not_found
        try:
            if alt_update is not None:
                # Executes an instance method.
                alt_update(instance, **data)
            else:
                instance.update(data)
            flash(instance.on_succesful_edit)
            return Status.succesful_edit
        except known_exceptions as e:
            app.logger.info(repr(e))
            db.session().rollback()
            flash(e.flash)
            return Status.failed_edit
        except Exception as e:
            app.logger.error(repr(e))
            db.session().rollback()
            # TODO: This should explain that the error is unknown.
            flash(instance.on_failed_edit)
            return Status.failed_edit
    else:
        app.logger.info("Form is used to create a new entity.")
        try:
            if alt_create is not None:
                # Executes a class method.
                instance = alt_create(**data)
            else:
                instance = object.create(data)
            flash(instance.on_succesful_create)
            return Status.succesful_create
        except known_exceptions as e:
            app.logger.info(repr(e))
            db.session().rollback()
            flash(e.flash)
            return Status.failed_create
        except Exception as e:
            app.logger.error(repr(e))
            db.session().rollback()
            # TODO: This should explain that the error is unknown.
            flash(instance.on_failed_create)
            return Status.failed_create
