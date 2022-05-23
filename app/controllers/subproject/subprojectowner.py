from typing import List

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import Status, process_form, BaseHandler
from app.forms import AddUserForm, EditUserForm
from app.models import Subproject, User
from app.util import formatted_flash


class SubprojectOwnerFormHandler(BaseHandler):
    def on_delete(self):
        raise NotImplementedError

    def on_update(self):
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        instance.edit_subproject_owner(**self.data)
        formatted_flash(f"Gebruiker {instance.email} is aangepast.", color="green")
        return Status.succesful_edit

    def on_create(self) -> Status:
        instance = User.add_user(**self.data)
        formatted_flash(
            f"Gebruiker '{instance.email}' is toegevoegd als activiteitnemer.",
            color="green",
        )
        return Status.succesful_create


class SubprojectOwnerController(Controller):
    def __init__(self, subproject: Subproject):
        self.subproject = subproject
        # Using two different forms: AddUserForm and EditProjectOwnerForm. In my
        # opinion, there should be only one form to edit the User model...
        self.add_form = AddUserForm(prefix="add_user_form")
        self.edit_form = EditUserForm(prefix="edit_project_owner_form")
        self.redirects = create_redirects_for_project_or_subproject(
            self.subproject.project_id, self.subproject.id
        )
        self.emails: List[str] = []

    def add(self):
        status = process_form(SubprojectOwnerFormHandler(self.add_form, User))
        return self.redirects[status]

    def edit(self):
        status = process_form(SubprojectOwnerFormHandler(self.edit_form, User))
        return self.redirects[status]

    def get_forms(self):
        forms: List[EditUserForm] = []
        for subproject_owner in self.subproject.users:
            data = {
                **subproject_owner.__dict__,
                **{"subproject_id": self.subproject.id},
            }
            forms.append(EditUserForm(prefix="edit_project_owner_form", **data))
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
        # Not implemented for EditUserForm. Errors shouldn't be able to happen.
        if len(self.add_form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#activiteitnemers-beheren", "#activiteitnemer-toevoegen"])
        return modals
