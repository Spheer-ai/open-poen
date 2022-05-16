from app.controllers.util import Controller, create_redirects_for_response
from app.form_processing import process_form, Status
from app.models import Project
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField, RadioField, IntegerField
from wtforms.widgets import HiddenInput
from app.util import form_in_request
from flask import request, redirect, url_for
from app import app


class JustifyProjectForm(FlaskForm):
    id = IntegerField(widget=HiddenInput())
    funders = RadioField(choices=[])
    concept = SubmitField(
        "Conceptversie downloaden", render_kw={"class": "btn btn-danger"}
    )
    send = SubmitField("Verantwoording versturen", render_kw={"class": "btn btn-info"})

    has_errors = False


class ConceptJustifyProjectForm(FlaskForm):
    id = IntegerField(widget=HiddenInput())
    funders = RadioField(choices=[])
    concept = SubmitField(
        "Conceptversie downloaden", render_kw={"class": "btn btn-danger"}
    )
    send = SubmitField(
        "Tussentijdse rapportage verzenden", render_kw={"class": "btn btn-info"}
    )

    has_errors = False


class JustifyProjectController(Controller):
    def __init__(self, project: Project):
        # TODO: Permissions.
        # self.clearance = clearance
        self.project = project
        self.justify_form = JustifyProjectForm(id=project.id, prefix="justify")
        self.concept_justify_form = ConceptJustifyProjectForm(
            id=project.id, prefix="concept-justify"
        )
        self.redirects = create_redirects_for_response(
            redirect(url_for("profile_project", project_id=self.project.id))
        )
        funders = self.project.funders.all()

        self.funder_info = {}
        for funder in funders:
            subprojects = funder.subprojects.all()
            unfinished_subproject = any([not x.finished for x in subprojects])
            funder.eligible = False if unfinished_subproject else True
            self.funder_info[funder.id] = {
                "name": f"{funder.subsidy_number} - {funder.name}",
                "subprojects": [x.name for x in subprojects],
                "eligible": funder.eligible,
            }

        all_choices = [(str(x.id), f"{x.subsidy_number} - {x.name}") for x in funders]
        eligible_choices = [
            x for x, funder in zip(all_choices, funders) if funder.eligible
        ]
        self.justify_form.funders.choices = eligible_choices
        try:
            self.justify_form.funders.default = eligible_choices[0][0]
        except IndexError:
            pass
        self.concept_justify_form.funders.choices = all_choices
        try:
            self.concept_justify_form.funders.default = all_choices[0][0]
        except IndexError:
            pass

        # Otherwise the CSRF token is removed when this form is submitted.
        if not form_in_request(self.justify_form, request):
            self.justify_form.process()
        if not form_in_request(self.concept_justify_form, request):
            self.concept_justify_form.process()

    def process(self, form):
        status = process_form(form, Project, alt_update=Project.justify)
        return self.redirects[status]

    def get_forms(self):
        if len(self.justify_form.errors) > 0:
            self.justify_form.has_errors = True
        return self.justify_form

    def get_concept_justify_form(self):
        if len(self.concept_justify_form.errors) > 0:
            self.concept_justify_form.has_errors = True
        return self.concept_justify_form

    def process_forms(self):
        redirect = self.process(self.justify_form)
        if redirect:
            return redirect
        redirect = self.process(self.concept_justify_form)
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.justify_form.errors) > 0:
            assert len(modals) == 0
            modals.append("#justify-project")
        elif len(self.concept_justify_form.errors) > 0:
            assert len(modals) == 0
            modals.append("#concept-justify-project")
        return modals
