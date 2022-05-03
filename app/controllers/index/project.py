from app.controllers.util import Controller
from app.forms import (
    trim_whitespace,
    validate_budget,
    validate_card_number,
    validate_card_number_to_project,
)
from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.fields.core import FieldList, FormField
from wtforms.validators import URL, DataRequired, Length, Optional
from wtforms.widgets import HiddenInput
from app.util import Clearance, form_in_request
from app.form_processing import process_form
from flask import url_for, redirect, request


class Funder(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    url = StringField("URL", validators=[DataRequired(), URL(), Length(max=2000)])


class DebitCard(FlaskForm):
    card_number = StringField(
        "Pasnummer",
        validators=[
            DataRequired(),
            validate_card_number_to_project,
            validate_card_number,
        ],
        filters=[trim_whitespace],
    )
    project_id = IntegerField(widget=HiddenInput(), validators=[Optional()])
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class Subproject(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Beschrijving", validators=[DataRequired()])
    hidden = BooleanField("Activiteit verbergen")
    budget = IntegerField(
        "Budget voor deze activiteit", validators=[Optional(), validate_budget]
    )


class Project(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Beschrijving", validators=[DataRequired()])
    contains_subprojects = BooleanField(
        "Uitgaven van dit initiatief worden geregistreerd op activiteiten",
        default="checked",
    )
    hidden = BooleanField("Initiatief verbergen")
    hidden_sponsors = BooleanField("Sponsoren verbergen")
    budget = IntegerField(
        "Budget voor dit initiatief", validators=[Optional(), validate_budget]
    )
    card_numbers = FieldList(
        FormField(DebitCard), min_entries=0, max_entries=None, validators=[]
    )
    funders = FieldList(
        FormField(Funder), min_entries=0, max_entries=None, validators=[]
    )
    subprojects = FieldList(
        FormField(Subproject),
        min_entries=0,
        max_entries=None,
        validators=[],
    )
    id = IntegerField(widget=HiddenInput())
    submit = SubmitField(
        "Opslaan", render_kw={"class": "btn btn-info interactive-submit"}
    )

    has_errors = False


class ProjectController(Controller):
    def __init__(self, clearance: Clearance):
        self.clearance = clearance
        self.form = Project()
        if not form_in_request(self.form, request):
            self.form.card_numbers.append_entry()
            self.form.funders.append_entry()
            self.form.subprojects.append_entry()

    def process(self, form):
        status = process_form(form, Project)
        if status is not None:
            return redirect(url_for("index"))

    def get_forms(self):
        if len(self.form.errors) > 0:
            self.form.has_errors = True
        return self.form

    def process_forms(self):
        redirect = self.process(self.form)
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.append("#modal-project-toevoegen")
        return modals
