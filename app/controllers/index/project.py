from app.controllers.util import Controller
from app.controllers.forms import FunderForm, SubprojectBaseForm
from app.form_processing import process_form, BaseHandler, Status
from app.forms import (
    trim_whitespace,
    validate_budget,
    validate_card_number,
    validate_card_number_to_project,
)
from app.models import Project
from app.util import Clearance, form_in_request, formatted_flash
from flask import redirect, request, url_for
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.fields.core import FieldList, FormField
from wtforms.validators import URL, DataRequired, Email, Length, Optional
from wtforms.widgets import HiddenInput

ALLOWED_EXTENSIONS = ["pdf", "xls", "xlsx"]


class DebitCard(FlaskForm):
    class Meta:
        csrf = False

    card_number = StringField(
        "Pasnummer",
        validators=[
            DataRequired(),
            validate_card_number_to_project,
            validate_card_number,
        ],
        filters=[trim_whitespace],
    )
    # TODO: check all card numbers are unique.


class ProjectOwner(FlaskForm):
    class Meta:
        csrf = False

    email = StringField(
        "E-mailadres initiatiefnemer",
        validators=[DataRequired(), Email(), Length(max=120)],
    )


class ProjectForm(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Beschrijving", validators=[DataRequired()])
    purpose = TextAreaField("Doel", validators=[DataRequired()])
    target_audience = TextAreaField("Doelgroep", validators=[DataRequired()])
    hidden = BooleanField("Initiatief verbergen")
    contains_subprojects = BooleanField(
        "Uitgaven van dit initiatief worden geregistreerd op activiteiten",
        default="checked",
    )
    funders = FieldList(
        FormField(FunderForm), min_entries=0, max_entries=None, validators=[]
    )
    hidden_sponsors = BooleanField("Sponsoren verbergen")

    card_numbers = FieldList(
        FormField(DebitCard), min_entries=0, max_entries=None, validators=[]
    )
    owner = StringField("Beheerder", validators=[DataRequired(), Length(max=120)])
    owner_email = StringField(
        "E-mailadres", validators=[DataRequired(), Email(), Length(max=120)]
    )
    project_owners = FieldList(
        FormField(ProjectOwner),
        min_entries=0,
        max_entries=None,
    )
    legal_entity = SelectField(
        "Rechtsvorm", choices=[("Stichting", "Stichting"), ("Vereniging", "Vereniging")]
    )
    address_applicant = StringField(
        "Adres aanvrager", validators=[DataRequired(), Length(max=120)]
    )
    registration_kvk = StringField(
        "Inschrijving KvK", validators=[DataRequired(), Length(max=120)]
    )
    project_location = StringField(
        "Locatie initiatief", validators=[DataRequired(), Length(max=120)]
    )

    budget_file = FileField(
        "Begroting",
        validators=[
            FileAllowed(
                ALLOWED_EXTENSIONS,
                (
                    "bestandstype niet toegstaan. Enkel de volgende "
                    "bestandstypen worden geaccepteerd: %s"
                    % ", ".join(ALLOWED_EXTENSIONS)
                ),
            ),
        ],
    )
    budget = IntegerField(
        "Totaal budget initiatief", validators=[Optional(), validate_budget]
    )

    id = IntegerField(widget=HiddenInput())
    submit = SubmitField(
        "Opslaan", render_kw={"class": "btn btn-info interactive-submit"}
    )

    has_errors = False


class ProjectFormHandler(BaseHandler):
    def on_delete(self):
        raise NotImplementedError

    def on_update(self):
        raise NotImplementedError

    def on_create(self) -> Status:
        Project.add_project(**self.data)
        formatted_flash("Initiatief is succesvol toegevoegd!", color="green")
        return Status.succesful_create


class ProjectController(Controller):
    def __init__(self, clearance: Clearance):
        self.clearance = clearance
        self.form = ProjectForm()
        if not form_in_request(self.form, request):
            self.form.card_numbers.append_entry()
            self.form.funders.append_entry()
            for _ in range(0, 3):
                self.form.project_owners.append_entry()

    def process(self, form):
        # TODO: Handle attachment.
        # del form["budget_file"]
        status = process_form(ProjectFormHandler(form, Project))
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
