from app.controllers.util import Controller, create_redirects_for_response
from app.form_processing import process_form, Status, BaseHandler
from app.models import Project
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField, RadioField, IntegerField
from wtforms.widgets import HiddenInput
from app.util import form_in_request, formatted_flash
from flask import request, redirect, url_for


class JustifyProjectForm(FlaskForm):
    id = IntegerField(widget=HiddenInput())
    funder = RadioField(choices=[])
    concept = SubmitField(
        "Conceptversie bekijken", render_kw={"class": "btn btn-danger"}
    )
    justify = SubmitField("Verantwoorden", render_kw={"class": "btn btn-info"})

    has_errors = False


class ConceptJustifyProjectForm(FlaskForm):
    id = IntegerField(widget=HiddenInput())
    funder = RadioField(choices=[])
    download = SubmitField(
        "Tussentijdse rapportage bekijken", render_kw={"class": "btn btn-danger"}
    )

    has_errors = False


class JustifyProjectFormHandler(BaseHandler):
    # Not filtering submit fields because we use those for programming logic.
    fields_to_filter = ["CSRFTokenField"]

    def on_delete(self):
        raise NotImplementedError

    def on_update(self):
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        instance.justify(**self.data)
        if self.data["justify"]:
            formatted_flash("Gefeliciteerd! De sponsor is verantwoord.", color="green")
        return Status.succesful_edit

    def on_create(self) -> Status:
        raise NotImplementedError


class ConceptJustifyProjectFormHandler(BaseHandler):
    # Not filtering submit fields because we use those for programming logic.
    fields_to_filter = ["CSRFTokenField"]

    def on_delete(self):
        raise NotImplementedError

    def on_update(self):
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        instance.concept_justify(**self.data)
        return Status.succesful_edit

    def on_create(self) -> Status:
        raise NotImplementedError


class JustifyProjectController(Controller):
    def __init__(self, project: Project):
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
            self.funder_info[funder.id] = {
                "name": f"{funder.subsidy_number} - {funder.name}",
                "subprojects": [x.name for x in subprojects],
                "can_be_justified": funder.can_be_justified,
            }

        all_choices = [(str(x.id), f"{x.subsidy_number} - {x.name}") for x in funders]
        conceptually_justifiable_choices = [
            x
            for x, funder in zip(all_choices, funders)
            if funder.has_at_least_one_subproject
        ]
        justifiable_choices = [
            x for x, funder in zip(all_choices, funders) if funder.can_be_justified
        ]
        self.justify_form.funder.choices = justifiable_choices
        try:
            self.justify_form.funder.default = justifiable_choices[0][0]
        except IndexError:
            pass
        self.concept_justify_form.funder.choices = conceptually_justifiable_choices
        try:
            self.concept_justify_form.funder.default = conceptually_justifiable_choices[
                0
            ][0]
        except IndexError:
            pass

        # Otherwise the CSRF token is removed when this form is submitted.
        if not form_in_request(self.justify_form, request):
            self.justify_form.process()
        if not form_in_request(self.concept_justify_form, request):
            self.concept_justify_form.process()

    def justify(self):
        status = process_form(JustifyProjectFormHandler(self.justify_form, Project))
        return self.redirects[status]

    def concept_justify(self):
        status = process_form(
            ConceptJustifyProjectFormHandler(self.concept_justify_form, Project)
        )
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
        redirect = self.justify()
        if redirect:
            return redirect
        redirect = self.concept_justify()
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
