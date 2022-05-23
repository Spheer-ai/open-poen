from flask_wtf import FlaskForm
from wtforms.fields import SubmitField, BooleanField, IntegerField
from wtforms import TextAreaField
from wtforms.validators import DataRequired
from wtforms.widgets import HiddenInput
from app.models import Subproject
from app.controllers.forms import SubprojectBaseForm
from app.controllers.util import Controller, create_redirects_for_response
from app.form_processing import process_form, BaseHandler, Status
from flask import redirect, url_for
from app.util import formatted_flash


class FinishSubprojectForm(SubprojectBaseForm):
    # TODO: Validator for amount of words.
    finished_description = TextAreaField(
        "Beschrijving (max. 250 woorden)",
        validators=[DataRequired()],
        render_kw={"style": "height: 150px;"},
    )
    finished = BooleanField(widget=HiddenInput())
    submit = SubmitField(
        "Afronden", render_kw={"class": "btn btn-info interactive-submit"}
    )

    has_errors = False


class UndoFinishSubprojectForm(FlaskForm):
    id = IntegerField(widget=HiddenInput())
    finished = BooleanField(widget=HiddenInput(), false_values=["y"])
    submit = SubmitField("Openen", render_kw={"class": "btn btn-info"})


class FinishSubprojectFormHandler(BaseHandler):
    # Not filtering submit fields because we use those for programming logic.
    fields_to_filter = ["CSRFTokenField"]

    def on_update(self) -> Status:
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        instance.update(self.data)
        formatted_flash(
            f"Gefeliciteerd! Activiteit '{instance.name}' is afgerond.", color="green"
        )
        return Status.succesful_edit


class UndoFinishSubprojectFormHandler(BaseHandler):
    # Not filtering submit fields because we use those for programming logic.
    fields_to_filter = ["CSRFTokenField"]

    def on_update(self) -> Status:
        instance = self.object.query.get(self.form.id.data)
        if instance is None:
            return Status.not_found
        instance.update(self.data)
        formatted_flash(
            f"Activiteit '{instance.name}' is opnieuw geopend.", color="green"
        )
        return Status.succesful_edit


class FinishSubprojectController(Controller):
    def __init__(self, subproject: Subproject):
        # TODO: Permissions.
        # self.clearance = clearance
        self.subproject = subproject
        self.finish_form = FinishSubprojectForm(
            prefix="finish_subproject", **self.subproject.__dict__
        )
        self.undo_form = UndoFinishSubprojectForm(
            prefix="undo_finish_subproject", id=self.subproject.id
        )
        self.redirects = create_redirects_for_response(
            redirect(url_for("profile_subproject", subproject_id=self.subproject.id))
        )
        self.funders = self.subproject.funders.all()

    def finish(self):
        status = process_form(FinishSubprojectFormHandler(self.finish_form, Subproject))
        return self.redirects[status]

    def undo_finish(self):
        status = process_form(
            UndoFinishSubprojectFormHandler(self.undo_form, Subproject)
        )
        return self.redirects[status]

    def get_forms(self):
        if len(self.finish_form.errors) > 0:
            self.finish_form.has_errors = True
        return self.finish_form

    def process_forms(self):
        redirect = self.finish()
        if redirect:
            return redirect
        redirect = self.undo_finish()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.finish_form.errors) > 0:
            assert len(modals) == 0
            modals.append("#finish-subproject")
        if len(self.undo_form.errors) > 0:
            assert len(modals) == 0
            modals.append("#undo-finish-subproject")
        return modals
