from typing import Dict, Type

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import process_form
from app.forms import validate_budget
from app.models import Funder, Project
from app.util import Clearance
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField
from wtforms.validators import URL, DataRequired, Length
from wtforms.widgets import HiddenInput


class BaseForm(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    url = StringField(
        "URL (format: http(s)://voorbeeld.com)",
        validators=[DataRequired(), URL(), Length(max=2000)],
    )
    subsidy = StringField(
        "Subsidieregeling", validators=[DataRequired(), Length(max=120)]
    )
    subsidy_number = StringField(
        "Beschikkingsnummer", validators=[DataRequired(), Length(max=120)]
    )
    budget = IntegerField(
        "Budget voor deze sponsor", validators=[DataRequired(), validate_budget]
    )
    id = IntegerField(widget=HiddenInput())
    project_id = IntegerField(widget=HiddenInput())
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})
    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})

    clearance = Clearance.PROJECT_OWNER


class FunderController(Controller):
    def __init__(self, project: Project, clearance: Clearance):
        self.project = project
        self.clearance = clearance
        self.form_class = self.form_permissions[clearance]
        self.add_form = self.form_class(prefix="add_funder_form", project_id=project.id)
        self.edit_form = self.form_class(
            prefix=f"edit_funder_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects_for_project_or_subproject(
            self.project.id, None
        )

    def process(self, form):
        status = process_form(form, Funder)
        return self.redirects[status]

    def get_forms(self):
        forms: Dict[int, self.form_class] = {}
        for funder in self.project.funders:
            data = funder.__dict__
            id = data["id"]
            forms[id] = self.form_class(prefix=f"edit_funder_form_{id}", **data)

        # If a funder has previously been edited with an error, we have to insert it.
        if len(self.edit_form.errors) > 0:
            forms[self.get_id_of_submitted_form] = self.edit_form

        return list(forms.values())

    def process_forms(self):
        redirect = self.process(self.add_form)
        if redirect:
            return redirect
        redirect = self.process(self.edit_form)
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.add_form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#sponsoren-beheren", "#sponsor-toevoegen"])
        elif len(self.edit_form.errors) > 0:
            assert len(modals) == 0
            modals.extend(
                ["#sponsoren-beheren", f"#sponsor-beheren-{self.edit_form.id.data}"]
            )
        return modals

    form_permissions: Dict[Clearance, Type[BaseForm]] = {
        Clearance.ANONYMOUS: BaseForm,
        Clearance.SUBPROJECT_OWNER: BaseForm,
        Clearance.PROJECT_OWNER: BaseForm,
        Clearance.FINANCIAL: BaseForm,
        Clearance.ADMIN: BaseForm,
    }
