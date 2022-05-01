from typing import Dict, Union, Type

from flask_login import current_user

from app.controllers.util import Controller, create_redirects
from app.form_processing import process_form
from app.forms import PaymentForm, NewPaymentForm
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
        payment = Payment.query.get(self.get_id_of_submitted_form)
        form_class = self.get_right_form(payment)
        self.edit_form = form_class(
            prefix=f"edit_payment_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects(
            self.subproject.project.id, self.subproject.id
        )

    def get_right_form(self, payment: Union[Payment, None]) -> Type[ImportedBNGPayment]:
        if payment is None or payment.type == "BNG":
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

    def add_payment(self):
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

    def edit(self):
        payment = Payment.query.get(self.edit_form.id.data)

        # This is necessary because a Selectfield's choices have to be set. Otherwise
        # the form will be invalid.
        if payment is None and form_in_request(self.edit_form, request):
            return self.redirects[Status.not_found]
        elif payment and form_in_request(self.edit_form, request):
            self.edit_form.category_id.choices = payment.make_category_select_options()
            self.edit_form.subproject_id.choices = (
                payment.make_subproject_select_options(self.subproject_owner_id)
            )

        status = process_form(self.edit_form, Payment)
        return self.redirects[status]

    def get_forms(self):
        forms: Dict[int, PaymentForm] = {}
        # TODO: Make sure only the payments for the user's permissions are returned.
        # AKA: Editable payments.
        for payment in self.subproject.payments:
            data = payment.__dict__
            id = data["id"]
            form_class = self.get_right_form(payment)
            form = form_class(prefix=f"edit_payment_form_{id}", **data)
            form.category_id.choices = payment.make_category_select_options()
            form.subproject_id.choices = payment.make_subproject_select_options(
                self.subproject_owner_id
            )
            forms[id] = form

        # If a payment has previously been edited with an error, we have to insert it.
        if len(self.edit_form.errors) > 0:
            forms[self.get_id_of_submitted_form] = self.edit_form

        return forms

    def process_forms(self):
        redirect = self.add_payment()
        if redirect:
            return redirect
        redirect = self.edit()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.add_payment_form.errors) > 0:
            assert len(modals) == 0
            modals.append("#modal-betaling-toevoegen")
        return modals

    def get_payment_id(self):
        if len(self.edit_form.errors) > 0:
            return self.edit_form.id.data
