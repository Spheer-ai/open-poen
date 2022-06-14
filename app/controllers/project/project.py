from typing import Dict, Type
from app.controllers.forms import LEGAL_ENTITIES, validate_kvk

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import Status, process_form, BaseHandler
from app.forms import validate_budget
from app.models import Project
from app.util import Clearance
from flask import redirect, url_for
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    StringField,
    SubmitField,
    TextAreaField,
    SelectField,
)
from wtforms.validators import DataRequired, Length, Optional, Email
from wtforms.widgets import HiddenInput

ALLOWED_EXTENSIONS = [".pdf", ".xls", ".xlsx"]


class BaseForm(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Beschrijving", validators=[DataRequired()])
    id = IntegerField(widget=HiddenInput())
    project_id = IntegerField(widget=HiddenInput())
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})

    clearance = Clearance.PROJECT_OWNER


class Admin(BaseForm):
    hidden = BooleanField("Initiatief verbergen")
    hidden_sponsors = BooleanField("Sponsoren verbergen")
    # TODO: No design for these new fields. Should this be admin? Should this be here?
    owner = StringField("Beheerder", validators=[DataRequired(), Length(max=120)])
    owner_email = StringField(
        "E-mailadres", validators=[DataRequired(), Email(), Length(max=120)]
    )
    legal_entity = SelectField("Rechtsvorm", choices=LEGAL_ENTITIES)
    address_applicant = StringField(
        "Adres aanvrager", validators=[DataRequired(), Length(max=120)]
    )
    registration_kvk = StringField(
        "Inschrijving KvK (Optioneel in het geval van een natuurlijk persoon.)",
        validators=[validate_kvk, Length(max=120)],
    )
    project_location = StringField(
        "Locatie initiatief", validators=[DataRequired(), Length(max=120)]
    )
    # TODO: Budget file.
    budget = IntegerField(
        "Budget voor dit initiatief (Format: 1000,00)",
        validators=[Optional(), validate_budget],
    )
    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})

    clearance = Clearance.ADMIN


class ProjectController(Controller):
    def __init__(self, project: Project, clearance: Clearance):
        self.project = project
        self.clearance = clearance
        self.form_class = self.form_permissions[clearance]
        self.form = self.form_class(prefix="project_form")
        self.redirects = create_redirects_for_project_or_subproject(
            self.project.id, None
        )
        self.redirects[Status.succesful_delete] = redirect(url_for("index"))

    def process(self, form):
        status = process_form(BaseHandler(form, Project))
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            form = self.form
        else:
            form = self.form_class(prefix="project_form", **self.project.__dict__)
        return form

    def process_forms(self):
        redirect = self.process(self.form)
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#project-beheren"])
        return modals

    # TODO: The way we do it now, only differences in fields of the form itself,
    # related to permissions, are regulated here. The question however if the form
    # should be rendered AT ALL, should be resolved in the template itself.
    form_permissions: Dict[Clearance, Type[BaseForm]] = {
        Clearance.ANONYMOUS: BaseForm,
        Clearance.SUBPROJECT_OWNER: BaseForm,
        Clearance.PROJECT_OWNER: BaseForm,
        Clearance.FINANCIAL: BaseForm,
        Clearance.ADMIN: Admin,
    }
