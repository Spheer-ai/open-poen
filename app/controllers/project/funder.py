from app.controllers.util import Controller, create_redirects
from app.forms import FunderForm
from app.models import Project, Funder
from app.form_processing import process_form


class FunderController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.add_form = FunderForm(prefix="add_funder_form", project_id=project.id)
        self.edit_form = FunderForm(
            prefix=f"edit_funder_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects(self.project.id, None)

    def add(self):
        status = process_form(self.add_form, Funder)
        return self.redirects[status]

    def edit(self):
        status = process_form(self.edit_form, Funder)
        return self.redirects[status]

    def get_forms(self):
        forms = {}
        for funder in self.project.funders:
            data = funder.__dict__
            id = data["id"]
            forms[id] = FunderForm(prefix=f"edit_funder_form_{id}", **data)

        # If a funder has previously been edited with an error, we have to insert it.
        if len(self.edit_form.errors) > 0:
            forms[self.get_id_of_submitted_form] = self.edit_form

        return list(forms.values())

    def process_forms(self):
        redirect = self.add()
        if redirect:
            return redirect
        redirect = self.edit()
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
