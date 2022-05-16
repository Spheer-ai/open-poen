from typing import Dict, List

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import process_form
from app.forms import CategoryForm
from app.models import Category, Project, Subproject


class CategoryController(Controller):
    def __init__(self, subproject: Subproject):
        self.subproject = subproject
        self.add_form = CategoryForm(
            prefix="add_category_form", subproject_id=self.subproject.id
        )
        self.edit_form = CategoryForm(
            prefix=f"edit_category_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects_for_project_or_subproject(
            self.subproject.project_id, self.subproject.id
        )
        self.names: List[str] = []

    def add(self):
        status = process_form(self.add_form, Category)
        return self.redirects[status]

    def edit(self):
        status = process_form(self.edit_form, Category)
        return self.redirects[status]

    def get_forms(self):
        forms: Dict[int, CategoryForm] = {}
        for category in self.subproject.categories:
            data = category.__dict__
            id = data["id"]
            forms[id] = CategoryForm(prefix=f"edit_category_form_{id}", **data)
            self.names.append(data["name"])

        # If a category has previously been edited with an error, we have to insert it.
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
            modals.extend(["#subproject-beheren", "#categorie-toevoegen"])
        elif len(self.edit_form.errors) > 0:
            assert len(modals) == 0
            modals.extend(
                ["#subproject-beheren", f"#categorie-beheren-{self.edit_form.id.data}"]
            )
        return modals
