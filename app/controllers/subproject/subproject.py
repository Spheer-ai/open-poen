from app.controllers.util import Controller, create_redirects
from app.form_processing import Status, process_form, return_redirect
from app.models import Subproject
from flask_wtf import FlaskForm
import wtforms.validators as v
import wtforms as w
from wtforms.widgets import HiddenInput
from app.forms import validate_budget


class SubprojectForm(FlaskForm):
    name = w.StringField("Naam", validators=[v.DataRequired(), v.Length(max=120)])
    description = w.TextAreaField("Beschrijving", validators=[v.DataRequired()])
    purpose = w.TextAreaField("Doel", validators=[v.DataRequired()])
    target_audience = w.TextAreaField("Doelgroep", validators=[v.DataRequired()])
    hidden = w.BooleanField("Activiteit verbergen")
    budget = w.IntegerField(
        "Budget voor deze activiteit", validators=[v.Optional(), validate_budget]
    )
    project_id = w.IntegerField(widget=HiddenInput())
    id = w.IntegerField(widget=HiddenInput())
    submit = w.SubmitField(
        "Opslaan", render_kw={"class": "btn btn-info interactive-submit"}
    )
    remove = w.SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})


class SubprojectController(Controller):
    def __init__(self, subproject: Subproject):
        # Because we want all actions to refresh the page.
        self.subproject = subproject
        self.form = SubprojectForm(prefix="subproject_form")
        self.redirects = create_redirects(
            self.subproject.project_id, self.subproject.id
        )
        # Except for a deletion, because after that the subproject page returns a 404.
        self.redirects[Status.succesful_delete] = return_redirect(
            self.subproject.project_id, None
        )

    def process(self):
        status = process_form(self.form, Subproject)
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            return self.form
        else:
            return SubprojectForm(prefix="subproject_form", **self.subproject.__dict__)

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#subproject-beheren"])
        return modals
