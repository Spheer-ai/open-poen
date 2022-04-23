from app.controllers.util import Controller, create_redirects
from app.forms import SubprojectForm
from app.models import Subproject
from app.form_processing import process_form, Status, return_redirect


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
