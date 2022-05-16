from xmlrpc.client import Boolean
from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import process_form
from app.forms import SubprojectForm
from app.models import Project, Subproject
from wtforms import BooleanField
from app.models import Funder


class SubprojectController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.form = SubprojectForm(prefix="subproject_form")
        self.form.funders.query = Funder.query.filter_by(
            project_id=self.project.id
        ).all()
        self.redirects = create_redirects_for_project_or_subproject(
            self.project.id, None
        )

    def process(self):
        status = process_form(self.form, Subproject)
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            self.form.has_errors = True
            return self.form
        else:
            form = SubprojectForm(
                prefix="subproject_form", **{"project_id": self.project.id}
            )
            form.funders.query = Funder.query.filter_by(
                project_id=self.project.id
            ).all()
            return form

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#subproject-toevoegen"])
        return modals
