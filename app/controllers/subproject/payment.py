from typing import Dict, Type

from flask_login import current_user

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import process_form
from app.forms import NewPaymentForm
from app.models import Payment, Subproject
from datetime import date
from app.controllers.util import Status
from app.controllers.project.payment import (
    ImportedBNGPayment,
    ManualPaymentOrTopup,
    ProjectOwnerPayment,
)
from app.util import Clearance, form_in_request
from flask import request


class PaymentController(Controller):
    def __init__(self, subproject: Subproject, clearance: Clearance):
        self.subproject = subproject
        self.clearance = clearance
        if self.clearance == Clearance.SUBPROJECT_OWNER:
            self.subproject_owner_id = current_user.id
        else:
            self.subproject_owner_id = None
        self.add_payment_form = NewPaymentForm(
            prefix="new_payment_form",
            project_id=self.subproject.project.id,
            subproject_id=self.subproject.id,
            booking_date=date.today(),
            type="MANUAL_PAYMENT",  # TODO: Make enum.
        )

        self.edit_forms = [
            ImportedBNGPayment(),
            ManualPaymentOrTopup(),
            ProjectOwnerPayment(),
        ]
        self.redirects = create_redirects_for_project_or_subproject(
            self.subproject.project.id, self.subproject.id
        )

    def add(self):
        # TODO: permissions check.
        # TODO: Handle attachment.
        del self.add_payment_form["mediatype"]
        del self.add_payment_form["data_file"]
        status = process_form(
            self.add_payment_form,
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
        forms: Dict[int, ImportedBNGPayment] = {}
        for payment in self.subproject.payments:
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
        redirect = self.add()
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
