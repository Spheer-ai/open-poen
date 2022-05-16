from typing import List

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import Status, process_form
from app.forms import AddUserForm, EditProjectOwnerForm
from app.models import Project, User
from app.util import formatted_flash


class ProjectOwnerController(Controller):
    def __init__(self, project: Project):
        self.project = project
        # Using two different forms: AddUserForm and EditProjectOwnerForm. In my
        # opinion, there should be only one form to edit the User model...
        self.add_form = AddUserForm(prefix="add_user_form")
        self.edit_form = EditProjectOwnerForm(prefix="edit_project_owner_form")
        self.redirects = create_redirects_for_project_or_subproject(
            self.project.id, None
        )
        self.emails: List[str] = []

    def add(self):
        status = process_form(self.add_form, User, alt_create=User.add_user)
        if status == Status.succesful_create:
            formatted_flash(
                "Gebruiker is succesvol toegevoegd als initiatiefnemer.", color="green"
            )
        return self.redirects[status]

    def edit(self):
        status = process_form(self.edit_form, User, alt_update=User.edit_project_owner)
        return self.redirects[status]

    def get_forms(self):
        forms: List[EditProjectOwnerForm] = []
        for project_owner in self.project.users:
            data = {**project_owner.__dict__, **{"project_id": self.project.id}}
            forms.append(EditProjectOwnerForm(prefix="edit_project_owner_form", **data))
            self.emails.append(data["email"])
        # Not inserting the form with an error because this shouldn't be able to happen.
        # See FunderController on how it should actually be done.
        return forms

    def process_forms(self):
        redirect = self.add()
        if redirect:
            return redirect
        redirect = self.edit()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        # Not implemented for EditProjectOwnerForm. Errors shouldn't be able to happen.
        if len(self.add_form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#project-beheren", "#project-owner-toevoegen"])
        return modals
