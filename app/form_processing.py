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
from app.models import BNGAccount, DebitCard, Funder, Project, Subproject
from app.util import formatted_flash


def filter_fields(form: FlaskForm) -> Dict:
    # Filter out these field names, because they are never saved in the DB.
    fields = {
        x.short_name: x.data
        for x in form
        if x.type not in ["SubmitField", "CSRFTokenField"]
    }
    # Set empty strings to None to keep everything consistent. Also, values like
    # foreign keys can't handle empty strings.
    return {key: (value if value != "" else None) for key, value in fields.items()}


def return_redirect(project_id: int, subproject_id: Union[None, int]):
    # Redirect back to clear form data
    if subproject_id:
        return redirect(
            url_for("subproject", project_id=project_id, subproject_id=subproject_id)
        )

    return redirect(url_for("project", project_id=project_id))


def process_new_project_form(form):
    if not util.validate_on_submit(form, request):
        return

    # We need to rerender the form if the user wants to add funders, debit cards or subprojects, but hasn't
    # received the rerendered form yet to actually enter those.
    # TODO: Refactor.
    rerender = False
    if form.funders_amount.data is not None:
        funders_to_add = form.funders_amount.data - len(form.funders)
        if funders_to_add > 0:
            for x in range(0, funders_to_add):
                form.funders.append_entry()
            rerender = True
    if form.card_numbers_amount.data is not None:
        debit_cards_to_add = form.card_numbers_amount.data - len(form.card_numbers)
        if debit_cards_to_add > 0:
            for x in range(0, debit_cards_to_add):
                form.card_numbers.append_entry()
            rerender = True
    if form.subprojects_amount.data is not None:
        subprojects_to_add = form.subprojects_amount.data - len(form.subprojects)
        if subprojects_to_add > 0:
            for x in range(0, subprojects_to_add):
                form.subprojects.append_entry()
            rerender = True
    if rerender:
        del form.funders_amount
        del form.card_numbers_amount
        del form.subprojects_amount
        form.errors["rerender"] = "rerender"
        return

    # TODO: We don't want this hardcoded.
    new_project_fields = [
        "name",
        "description",
        "contains_subprojects",
        "hidden",
        "hidden_sponsors",
        "budget",
    ]
    new_project_data = {
        x.short_name: x.data for x in form if x.short_name in new_project_fields
    }
    new_project = Project(**new_project_data)

    # Of all the cards entered, check whether they already exist. (Debit cards are created as payments are parsed.)
    # If they already exist, we just need to assign them to the project that we are creating. If they are already
    # assigned to a project, the user made a mistake. If the card does not exist yet, a payment for that card has
    # never been parsed yet, but that doesn't matter to the user, so we add it in advance.
    card_numbers = [x.card_number.data for x in form.card_numbers]
    already_existing_debit_cards = [
        x for x in DebitCard.query.all() if x.card_number in card_numbers
    ]
    new_debit_cards = [
        DebitCard(card_number=x)
        for x in card_numbers
        if x not in [i.card_number for i in already_existing_debit_cards]
    ]

    funders = [Funder(name=x.form.name.data, url=x.form.url.data) for x in form.funders]

    # TODO: We don't want this hardcoded.
    new_subproject_fields = ["name", "description", "hidden", "budget"]
    new_subproject_data = [
        {x.short_name: x.data for x in i if x.short_name in new_subproject_fields}
        for i in form.subprojects
    ]
    subprojects = [Subproject(**x) for x in new_subproject_data]
    if not len(subprojects) == len(set([x.name for x in subprojects])):
        formatted_flash(
            (
                "Minstens twee initiatieven hebben dezelfde naam. Geef elk initiatief "
                "een unieke naam om een project aan te maken."
            ),
            color="red",
        )
        return

    new_project.debit_cards = already_existing_debit_cards + new_debit_cards
    new_project.funders = funders
    new_project.subprojects = subprojects

    try:
        db.session.add(new_project)
        db.session.commit()
        formatted_flash(f"Project {new_project.name} is toegevoegd.", color="green")
        return redirect(url_for("index"))
    except (ValueError, IntegrityError) as e:
        app.logger.error(repr(e))
        db.session().rollback()
        # This should, in practise, be the only case possible that results in the aforementioned exceptions.
        formatted_flash(
            f"Het project is niet toegevoegd. Er bestaat al een project met de naam {new_project.name}.",
            color="red",
        )


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
