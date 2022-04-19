from abc import ABC, abstractmethod
from typing import Union
from app.forms import EditProjectForm, FunderForm, SubprojectForm
from app.form_processing import process_form
from app.models import Funder, Subproject, Project
import re
from flask import request


class Controller(ABC):
    @property
    def get_id_of_submitted_form(self):
        keys = list(request.form.keys())
        if len(keys) > 0:
            try:
                id = int(re.search("\d", keys[0]).group(0))
            except (IndexError, AttributeError):
                id = None
            return id
        else:
            return None

    @abstractmethod
    def get_forms(self):
        pass

    @abstractmethod
    def process_forms(self):
        pass

    @abstractmethod
    def get_modal_ids(self):
        pass


class FunderController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.add_form = FunderForm(prefix="add_funder_form", project_id=project.id)
        self.edit_form = FunderForm(
            prefix=f"edit_funder_form_{self.get_id_of_submitted_form}"
        )

    def add(self):
        return process_form(self.add_form, Funder)

    def edit(self):
        return process_form(self.edit_form, Funder)

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

    def process(self):
        return process_form(self.form, Project)

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

    def process(self):
        return process_form(self.form, Subproject)

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
