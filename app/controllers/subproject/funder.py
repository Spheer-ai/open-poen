from typing import Dict

from app import db
from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import process_form
from app.models import Funder, Subproject
from app.util import Clearance
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


class FunderController(Controller):
    def __init__(self, subproject: Subproject, clearance: Clearance):
        self.subproject = subproject
        self.clearance = clearance

        self.add_form = AddFunderForm(
            prefix="add_funder_form", subproject_id=self.subproject.id
        )
        linkable = db.session.query(Funder).filter(
            Funder.project_id == self.subproject.project.id
        )
        already_linked = [x.id for x in self.subproject.funders.all()]
        self.add_form.funders.query = linkable.filter(
            Funder.id.notin_(already_linked)
        ).all()

        self.edit_form = EditFunderForm(
            prefix=f"edit_funder_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects_for_project_or_subproject(
            self.subproject.project.id, self.subproject.id
        )
        self.funder_info: Dict[int, Dict] = {}

    def add(self):
        # TODO: Fix error message here.
        status = process_form(self.add_form, Funder, alt_create=Funder.attach)
        return self.redirects[status]

    def edit(self):
        status = process_form(self.edit_form, Funder, alt_update=Funder.detach)
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
