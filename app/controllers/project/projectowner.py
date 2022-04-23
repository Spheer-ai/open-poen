from app.controllers.util import Controller, create_redirects
from app.forms import EditProjectOwnerForm
from app.models import Project, User
from app.form_processing import process_form
from typing import List


class ProjectOwnerController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.form = EditProjectOwnerForm(prefix="edit_project_owner_form")
        self.redirects = create_redirects(self.project.id, None)
        self.emails: List[str] = []

    def process(self):
        status = process_form(self.form, User)
        return self.redirects[status]

    def get_forms(self):
        forms = []
        for project_owner in self.project.users:
            data = {**project_owner.__dict__, **{"project_id": self.project.id}}
            forms.append(EditProjectOwnerForm(prefix="edit_project_owner_form", **data))
            self.emails.append(data["email"])
        # Not inserting the form with an error because this shouldn't be able to happen.
        # See FunderController on how it should actually be done.
        return forms

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        # Not implemented. Errors shouldn't be able to happen.
        return modals
