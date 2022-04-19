from abc import ABC, abstractmethod
from typing import Union, List
from app.forms import EditProjectForm, EditProjectOwnerForm, FunderForm, SubprojectForm
from app.form_processing import process_form, Status, return_redirect
from app.models import Funder, Subproject, Project, User
import re
from flask import request
from flask.templating import render_template
from app import app
from flask_wtf import FlaskForm


class Controller(ABC):
    @property
    def get_id_of_submitted_form(self):
        keys = list(request.form.keys())
        if len(keys) > 0:
            try:
                id = int(re.search("\d+", keys[0]).group(0))
            except (IndexError, AttributeError):
                id = None
            return id
        else:
            return None

    @abstractmethod
    def get_forms(self) -> Union[FlaskForm, List[FlaskForm]]:
        pass

    @abstractmethod
    def process_forms(self):
        pass

    @abstractmethod
    def get_modal_ids(self):
        pass


def create_redirects(project_id: int, subproject_id: Union[None, int]):
    redirects = dict.fromkeys(
        [
            Status.succesful_delete,
            Status.succesful_edit,
            Status.failed_edit,
            Status.succesful_create,
            Status.failed_create,
        ],
        return_redirect(project_id, subproject_id),
    )
    redirects[Status.not_found] = render_template(
        "404.html",
        use_square_borders=app.config["USE_SQUARE_BORDERS"],
        footer=app.config["FOOTER"],
    )
    redirects[None] = None
    return redirects


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


class ProjectController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.form = EditProjectForm(prefix="project_form")
        # Because it's not allowed to change this property after instantiation.
        self.form.contains_subprojects.data = project.contains_subprojects
        self.redirects = create_redirects(self.project.id, None)

    def process(self):
        status = process_form(self.form, Project)
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            form = self.form
        else:
            form = EditProjectForm(prefix="project_form", **self.project.__dict__)
        # Make the user unable to change this property in the UI.
        form.contains_subprojects.render_kw = {"disabled": ""}
        return form

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#project-beheren"])
        return modals


class SubprojectProjectController(Controller):
    def __init__(self, project: Union[Project, Subproject]):
        self.project = project
        self.form = SubprojectForm(prefix="subproject_form")
        self.redirects = create_redirects(self.project.id, None)

    def process(self):
        status = process_form(self.form, Subproject)
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            return self.form
        else:
            return SubprojectForm(
                prefix="subproject_form", **{"project_id": self.project.id}
            )

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#subproject-toevoegen"])
        return modals


class SubprojectSubprojectController(SubprojectProjectController):
    def __init__(self, subproject: Subproject):
        super().__init__(subproject)
        # Because we want all actions to refresh the page.
        self.redirects = create_redirects(self.project.project_id, self.project.id)
        # Except for a deletion, because after that the subproject page returns a 404.
        self.redirects[Status.succesful_delete] = return_redirect(
            self.project.project_id, None
        )

    def get_forms(self):
        if len(self.form.errors) > 0:
            return self.form
        else:
            return SubprojectForm(prefix="subproject_form", **self.project.__dict__)

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#subproject-beheren"])
        return modals


class ProjectOwnerController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.form = EditProjectOwnerForm(prefix="edit_project_owner_form")
        self.redirects = create_redirects(self.project.id, None)
        self.emails = []

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
        # See FunderController.
        return forms

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        # Not implemented. Errors shouldn't be able to happen.
        return modals
