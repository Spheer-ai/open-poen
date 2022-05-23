from typing import Dict

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import BaseHandler, Status, process_form
from app.models import Funder, Subproject
from app.util import Clearance, formatted_flash
from flask_wtf import FlaskForm
from wtforms import IntegerField, SubmitField
from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField
from wtforms.widgets import CheckboxInput, HiddenInput


class EditFunderForm(FlaskForm):
    id = IntegerField(widget=HiddenInput())
    subproject_id = IntegerField(widget=HiddenInput())
    submit = SubmitField("Ontkoppelen", render_kw={"class": "btn btn-danger"})


class AddFunderForm(FlaskForm):
    funders = QuerySelectMultipleField(
        "Funder",
        option_widget=CheckboxInput(),
        get_label="name",
    )
    subproject_id = IntegerField(widget=HiddenInput())
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class FunderFormHandler(BaseHandler):
    def on_update(self) -> Status:
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        instance.detach(**self.data)
        formatted_flash(f"Sponsor '{instance.name}' is ontkoppeld.", color="green")
        return Status.succesful_create

    def on_create(self) -> Status:
        instance = Funder.attach(**self.data)
        formatted_flash(f"Sponsor '{instance.name}' is gekoppeld.", color="green")
        return Status.succesful_create


class FunderController(Controller):
    def __init__(self, subproject: Subproject, clearance: Clearance):
        self.subproject = subproject
        self.clearance = clearance

        self.add_form = AddFunderForm(
            prefix="add_funder_form", subproject_id=self.subproject.id
        )
        linkable = self.subproject.project.coupleable_funders
        already_linked = self.subproject.funders.all()
        self.add_form.funders.query = [x for x in linkable if x not in already_linked]

        self.edit_form = EditFunderForm(
            prefix=f"edit_funder_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects_for_project_or_subproject(
            self.subproject.project.id, self.subproject.id
        )
        self.funder_info: Dict[int, Dict] = {}

    def add(self):
        status = process_form(FunderFormHandler(self.add_form, Funder))
        return self.redirects[status]

    def edit(self):
        status = process_form(FunderFormHandler(self.edit_form, Funder))
        return self.redirects[status]

    def get_forms(self):
        forms: Dict[int, EditFunderForm] = {}
        for funder in self.subproject.funders:
            data = funder.__dict__
            id = data["id"]
            forms[id] = EditFunderForm(
                prefix=f"edit_funder_form_{id}",
                **data,
                subproject_id=self.subproject.id,
            )
            self.funder_info[id] = {"name": funder.name}

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
            modals.extend(["#sponsoren-beheren", "#sponsor-koppelen"])
        elif len(self.edit_form.errors) > 0:
            assert len(modals) == 0
            modals.extend(
                ["#sponsoren-beheren", f"#sponsor-ontkoppelen-{self.edit_form.id.data}"]
            )
        return modals
