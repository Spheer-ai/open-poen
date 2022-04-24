from typing import Dict

from app.controllers.util import Controller, create_redirects
from app.form_processing import process_form
from app.forms import PaymentForm, NewPaymentForm
from app.models import Payment, Project
from datetime import date


class PaymentController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.add_form = NewPaymentForm(
            prefix="new_payment_form",
            project_id=self.project.id,
            booking_date=date.today(),
            type="MANUAL",
        )
        self.edit_form = PaymentForm(
            prefix=f"edit_payment_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects(self.project.id, None)

    def add(self):
        # TODO: permissions check.
        # TODO: Handle attachment.
        del self.add_form["mediatype"]
        del self.add_form["data_file"]
        status = process_form(
            self.add_form, Payment, alt_create=Payment.add_manual_payment
        )
        return self.redirects[status]

    def edit(self):
        # TODO: Find a way to make category and subproject select options.
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
            if payment.type != "MANUAL":
                del form["booking_date"]
                del form["remove"]
            # TODO: Find a way to make category and subproject select options.
            forms[id] = form

        # If a payment has previously been edited with an error, we have to insert it.
        if len(self.edit_form.errors) > 0:
            forms[self.get_id_of_submitted_form] = self.edit_form

        return forms

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
            modals.append("#modal-topup-toevoegen")
        elif len(self.edit_form.errors) > 0:
            assert len(modals) == 0
            # TODO: return the payment id for popping it open.
        return modals
