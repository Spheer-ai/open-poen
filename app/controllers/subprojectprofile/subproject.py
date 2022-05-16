from flask_wtf import FlaskForm
from wtforms.fields.core import FieldList, FormField
from wtforms.fields import SubmitField
from wtforms import TextAreaField
from wtforms.validators import DataRequired
from app.models import Subproject
from app.controllers.forms import SubprojectBaseForm, FunderForm
from app.controllers.util import Controller, create_redirects_for_response
from app.util import Clearance, form_in_request
from app.form_processing import process_form
from flask import request, redirect, url_for


class FinishSubprojectForm(SubprojectBaseForm):
    funders = FieldList(
        FormField(FunderForm), min_entries=0, max_entries=None, validators=[]
    )
    # TODO: Validator for amount of words.
    ending_description = TextAreaField(
        "Beschrijving (max. 250 woorden)",
        validators=[DataRequired()],
        render_kw={"style": "height: 150px;"},
    )
    submit = SubmitField(
        "Opslaan", render_kw={"class": "btn btn-info interactive-submit"}
    )

    has_errors = False


class FinishSubprojectController(Controller):
    def __init__(self, subproject: Subproject):
        # TODO: Permissions.
        # self.clearance = clearance
        self.subproject = subproject
        self.form = FinishSubprojectForm(**self.subproject.__dict__)
        self.redirects = create_redirects_for_response(
            redirect(url_for("profile_subproject", subproject_id=self.subproject.id))
        )
        if not form_in_request(self.form, request):
            for funder in self.subproject.funders.all():
                self.form.funders.append_entry(
                    {k: v for k, v in funder.__dict__.items() if not k.startswith("_")}
                )

    def process(self, form):
        # TODO: Handle attachment.
        status = process_form(form, Subproject, alt_update=Subproject.finish)
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            self.form.has_errors = True
        return self.form

    def process_forms(self):
        redirect = self.process(self.form)
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.append("#finish-subproject")
        return modals
