from app.controllers.util import Controller, create_redirects
from app.form_processing import process_form
from flask_wtf import FlaskForm
from app.models import Project
from app.forms import validate_budget
from flask_wtf import FlaskForm
from wtforms.validators import (
    DataRequired,
    Length,
    Optional,
)
from wtforms.widgets import HiddenInput
from wtforms import (
    StringField,
    IntegerField,
    BooleanField,
    SubmitField,
    TextAreaField,
)
from app.util import Clearance, get_clearance


class BaseForm(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Beschrijving", validators=[DataRequired()])
    contains_subprojects = BooleanField(
        "Uitgaven van dit initiatief worden geregistreerd op activiteiten",
        render_kw={"checked": "", "value": "y"},
    )
    id = IntegerField(widget=HiddenInput())
    project_id = IntegerField(widget=HiddenInput())
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class Admin(BaseForm):
    hidden = BooleanField("Initiatief verbergen")
    hidden_sponsors = BooleanField("Sponsoren verbergen")
    budget = IntegerField(
        "Budget voor dit initiatief", validators=[Optional(), validate_budget]
    )
    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})


def get_form(project):
    # TODO: The way we do it now, only differences in fields of the form itself,
    # related to permissions, are regulated here. The question however if the form
    # should be rendered AT ALL, should be resolved in the template itself.
    clearance = get_clearance(project, None)
    if clearance >= Clearance.ADMIN:
        return Admin
    else:
        return BaseForm


class ProjectController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.form_class = get_form(self.project)
        self.form = self.form_class(prefix="project_form")
        # Because it's not allowed to change this property after instantiation.
        self.form.contains_subprojects.data = project.contains_subprojects
        self.redirects = create_redirects(self.project.id, None)

    def process(self):
        status = process_form(self.form, Project)
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            form = self.form
        else:
            form = self.form_class(prefix="project_form", **self.project.__dict__)
        # Make the user unable to change this property in the UI.
        form.contains_subprojects.render_kw = {"disabled": ""}
        return form

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#project-beheren"])
        return modals
