from enum import Enum
from time import time
from typing import Dict, List, Union

import jwt
from flask import Response, flash, redirect, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from requests import ConnectionError

from app import app
from app import bng as bng
from app import db, util
from app.exceptions import known_exceptions
from app.models import BNGAccount
from app.util import form_in_request, formatted_flash


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
        # bng.delete_consent(bng_account.consent_id, bng_account.access_token)

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


def filter_fields(form: FlaskForm, fields_to_filter: List[str]) -> Dict:
    # Filter out these field names, because they are never saved in the DB.
    fields = {x.short_name: x.data for x in form if x.type not in fields_to_filter}
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


class BaseHandler:
    fields_to_filter = ["SubmitField", "CSRFTokenField"]

    def __init__(self, form, object):
        self.form = form
        self.object = object
        self.form_in_request = form_in_request(self.form, request)

    def filter_fields(self):
        self.data = filter_fields(self.form, self.fields_to_filter)

    @property
    def delete(self) -> bool:
        return hasattr(self.form, "remove") and self.form.remove.data

    @property
    def update(self) -> bool:
        return hasattr(self.form, "id") and self.form.id.data

    @property
    def create(self) -> bool:
        return not hasattr(self.form, "id") or not self.form.id.data

    def on_delete(self) -> Status:
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        db.session.delete(instance)
        db.session.commit()
        flash(instance.on_succesful_delete)
        return Status.succesful_delete

    def on_update(self) -> Status:
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        instance.update(self.data)
        flash(instance.on_succesful_edit)
        return Status.succesful_edit

    def on_create(self) -> Status:
        instance = self.object.create(self.data)
        flash(instance.on_succesful_create)
        return Status.succesful_create


def process_form(handler: BaseHandler) -> Union[None, Status]:
    if not handler.form_in_request:
        return None

    app.logger.info(f"Form {str(handler.form)} for object {str(object)} is submitted.")

    if handler.delete:
        return handler.on_delete()

    if not handler.form.validate_on_submit():
        app.logger.info(
            f"Invalid form. Data: {handler.form.data}. Errors: {handler.form.errors}."
        )
        return None

    app.logger.info(f"Form is valid. Data: {handler.form.data}.")

    handler.filter_fields()

    if handler.update:
        app.logger.info("Form is used to edit an existing entity.")
        try:
            return handler.on_update()
        except known_exceptions as e:
            app.logger.info(repr(e))
            db.session().rollback()
            flash(e.flash)
            return Status.failed_edit
    elif handler.create:
        app.logger.info("Form is used to create a new entity.")
        try:
            return handler.on_create()
        except known_exceptions as e:
            app.logger.info(repr(e))
            db.session().rollback()
            flash(e.flash)
            return Status.failed_create
    else:
        raise AssertionError("Unaccounted for edge case in form handling.")
