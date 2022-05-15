from app.controllers.util import Controller
from app.form_processing import process_form
from app.models import Project
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField, RadioField
from app.util import form_in_request
from flask import request


class JustifyProjectForm(FlaskForm):
    funders = RadioField(choices=[])
    concept = SubmitField(
        "Conceptversie downloaden", render_kw={"class": "btn btn-danger"}
    )
    justify = SubmitField(
        "Verantwoording versturen", render_kw={"class": "btn btn-info"}
    )

    has_errors = False


class JustifyProjectController(Controller):
    def __init__(self, project: Project):
        # TODO: Permissions.
        # self.clearance = clearance
        self.project = project
        self.form = JustifyProjectForm()
        funders = self.project.funders.all()
        self.eligible_funder_count = 0
        self.eligible_funders = {}
        self.ineligible_funders = []
        for funder in funders:
            subprojects = funder.subprojects.all()
            unfinished_subproject = any([not x.finished for x in subprojects])
            if not unfinished_subproject:
                # For the form.
                self.form.funders.choices.append(
                    (str(funder.id), f"{funder.subsidy_number} - {funder.name}")
                )
                if self.form.funders.default is None:
                    self.form.funders.default = str(funder.id)
                # For the confirmation what activities will be justified.
                self.eligible_funders[funder.id] = {
                    "funder": f"{funder.subsidy_number} - {funder.name}",
                    "subprojects": [x.name for x in subprojects],
                }
            else:
                # For showing what funders are not shown because of incomplete
                # activities.
                self.ineligible_funders.append(
                    f"{funder.subsidy_number} - {funder.name}"
                )
        if not form_in_request(self.form, request):
            self.form.process()  # This removes the CSRF token if the form is being submitted.

    def process(self, form):
        status = process_form(form, Project, alt_update=Project.justify)
        return None

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
            modals.append("#justify-project")
        return modals
