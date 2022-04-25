from typing import Dict

from app.controllers.util import Controller, create_redirects
from app.form_processing import process_form
from app.forms import NewTopupForm, PaymentForm, NewPaymentForm
from app.models import Payment, Project
from datetime import date
from app.controllers.util import Status
from app.util import form_in_request
from flask import request


class PaymentController(Controller):
    def __init__(self, project: Project):
        self.project = project
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
        self.edit_form = PaymentForm(
            prefix=f"edit_payment_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects(self.project.id, None)

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

    def add_topup(self):
        # TODO: permissions check.
        # TODO: Handle attachment.
        del self.add_topup_form["mediatype"]
        del self.add_topup_form["data_file"]
        status = process_form(
            self.add_topup_form, Payment, alt_create=Payment.add_manual_topup_or_payment
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
                payment.make_subproject_select_options()
            )

        status = process_form(self.edit_form, Payment)
        return self.redirects[status]

    def get_forms(self):
        forms: Dict[int, PaymentForm] = {}
        # TODO: Make sure only the payments for the user's permissions are returned.
        # AKA: Editable payments.
        for payment in self.project.get_all_payments():
            data = payment.__dict__
            id = data["id"]
            form = PaymentForm(prefix=f"edit_payment_form_{id}", **data)
            if payment.type not in ("MANUAL_PAYMENT", "MANUAL_TOPUP"):
                del form["booking_date"]
                del form["remove"]
            form.category_id.choices = payment.make_category_select_options()
            form.subproject_id.choices = payment.make_subproject_select_options()
            forms[id] = form

        # If a payment has previously been edited with an error, we have to insert it.
        if len(self.edit_form.errors) > 0:
            forms[self.get_id_of_submitted_form] = self.edit_form

        return forms

    def process_forms(self):
        redirect = self.add_payment()
        if redirect:
            return redirect
        redirect = self.add_topup()
        if redirect:
            return redirect
        redirect = self.edit()
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
        if len(self.edit_form.errors) > 0:
            return self.edit_form.id.data
