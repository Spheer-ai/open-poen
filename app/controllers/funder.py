from abc import ABC, abstractmethod
from typing import List
from app.forms import FunderForm
from app.form_processing import process_form
from app.models import Funder
from app.util import form_in_request
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


class FunderController(Controller):
    def __init__(self, project):
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

    def get_modal_ids(self):
        modals = []
        if len(self.add_form.errors) > 0:
            modals.append("#sponsoren-beheren")
            modals.append("#sponsor-toevoegen")
        elif len(self.edit_form.errors) > 0:
            modals.append("#sponsoren-beheren")
            modals.append(f"#sponsor-beheren-{self.edit_form.id.data}")
        return modals
