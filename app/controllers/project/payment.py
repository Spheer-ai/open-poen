from datetime import date
from typing import Dict, Type

from app.controllers.util import Controller, Status, create_redirects
from app.form_processing import process_form
from app.forms import FlexibleDecimalField, NewPaymentForm, NewTopupForm
from app.models import Payment, Project
from app.util import Clearance, form_in_request
from flask import request
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import Length, Optional
from wtforms.widgets import HiddenInput


class ImportedBNGPayment(FlaskForm):
    short_user_description = StringField(
        "Korte beschrijving", validators=[Length(max=50)]
    )
    long_user_description = TextAreaField(
        "Lange beschrijving", validators=[Length(max=2000)]
    )
    hidden = BooleanField("Transactie verbergen")
    category_id = SelectField("Categorie", validators=[Optional()], choices=[])
    subproject_id = SelectField("Activiteit", validators=[Optional()], choices=[])
    id = IntegerField(widget=HiddenInput())
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "imported_bng"
        super().__init__(*args, **kwargs)


class ManualPaymentOrTopup(ImportedBNGPayment):
    route = SelectField(
        "Route",
        validators=[Optional()],
        choices=[
            ("inkomsten", "inkomsten"),
            ("uitgaven", "uitgaven"),
            ("inbesteding", "inbesteding"),
        ],
    )
    booking_date = DateField("Datum (notatie: dd-mm-jjjj)", format="%d-%m-%Y")
    transaction_amount = FlexibleDecimalField(
        'Bedrag (begin met een "-" als het een uitgave is)'
    )

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "manual_payment_or_topup"
        super(ImportedBNGPayment, self).__init__(*args, **kwargs)


class ProjectOwnerPayment(ManualPaymentOrTopup):
    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "project_owner"
        super(ImportedBNGPayment, self).__init__(*args, **kwargs)


class PaymentController(Controller):
    def __init__(self, project: Project, clearance: Clearance):
        self.project = project
        self.clearance = clearance
        if self.clearance == Clearance.SUBPROJECT_OWNER:
            self.subproject_owner_id = current_user.id
        else:
            self.subproject_owner_id = None
        self.add_payment_form = NewPaymentForm(
            prefix="new_payment_form",
            project_id=self.project.id,
            booking_date=date.today(),
            type="MANUAL_PAYMENT",  # TODO: Make enum.
        )
        self.add_topup_form = NewTopupForm(
            prefix="new_topup_form",
            project_id=self.project.id,
            booking_date=date.today(),
            type="MANUAL_TOPUP",  # TODO: Make enum.
        )
        self.add_topup_form.card_number.choices = (
            project.make_debit_card_select_options()
        )
        self.edit_forms = [
            ImportedBNGPayment(),
            ManualPaymentOrTopup(),
            ProjectOwnerPayment(),
        ]
        self.redirects = create_redirects(self.project.id, None)

    def add(self, form):
        # TODO: permissions check.
        # TODO: Handle attachment.
        del form["mediatype"]
        del form["data_file"]
        status = process_form(
            form,
            Payment,
            alt_create=Payment.add_manual_topup_or_payment,
        )
        return self.redirects[status]

    def edit(self, form):
        if form_in_request(form, request):
            payment = Payment.query.get(form.id.data)
            if not payment:
                return self.redirects[Status.not_found]
            # This is necessary because a Selectfield's choices have to be set.
            # Otherwise the form will be invalid.
            form.category_id.choices = payment.make_category_select_options()
            form.subproject_id.choices = payment.make_subproject_select_options(
                self.subproject_owner_id
            )

        status = process_form(form, Payment)
        return self.redirects[status]

    def get_forms(self):
        forms: Dict[int, Type[ImportedBNGPayment]] = {}
        for payment in self.project.get_all_payments():
            data = payment.__dict__
            id = data["id"]
            form_class = self.get_right_form(payment)
            form = form_class(formdata=None, **data)
            form.category_id.choices = payment.make_category_select_options()
            form.subproject_id.choices = payment.make_subproject_select_options(
                self.subproject_owner_id
            )
            forms[id] = form

        # If a payment has previously been edited with an error, we have to insert it.
        for form in self.edit_forms:
            if len(form.errors) > 0:
                forms[form.id.data] = form

        return forms

    def process_forms(self):
        redirect = self.add(self.add_payment_form)
        if redirect:
            return redirect
        redirect = self.add(self.add_topup_form)
        if redirect:
            return redirect
        for form in self.edit_forms:
            redirect = self.edit(form)
            if redirect:
                return redirect

    def get_modal_ids(self, modals):
        if len(self.add_payment_form.errors) > 0:
            assert len(modals) == 0
            modals.append("#modal-betaling-toevoegen")
        if len(self.add_topup_form.errors) > 0:
            assert len(modals) == 0
            modals.append("#modal-topup-toevoegen")
        return modals

    def get_payment_id(self):
        for form in self.edit_forms:
            if len(form.errors) > 0:
                return form.id.data

    def get_right_form(self, payment: Payment) -> Type[ImportedBNGPayment]:
        if payment.type == "BNG":
            return ImportedBNGPayment
        elif (
            payment.type in ("MANUAL_PAYMENT", "MANUAL_TOPUP")
            and self.clearance < Clearance.PROJECT_OWNER
        ):
            return ManualPaymentOrTopup
        elif (
            payment.type in ("MANUAL_PAYMENT", "MANUAL_TOPUP")
            and self.clearance >= Clearance.PROJECT_OWNER
        ):
            return ProjectOwnerPayment
        else:
            raise ValueError("Unaccounted for edge case in form selection for payment.")
