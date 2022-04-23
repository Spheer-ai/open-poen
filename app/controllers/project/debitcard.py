from typing import List

from app import db
from app.controllers.util import Controller, create_redirects
from app.form_processing import process_form
from app.forms import DebitCardForm, EditDebitCardForm
from app.models import DebitCard, Payment, Project
from app.util import calculate_amounts


class DebitCardController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.add_form = DebitCardForm(
            prefix="add_debit_card_form", project_id=self.project.id
        )
        self.edit_form = EditDebitCardForm(prefix="edit_debit_card_form")
        self.redirects = create_redirects(self.project.id, None)
        self.debit_card_numbers: List[str] = []
        self.debit_cards: List[DebitCard] = []

    def add(self):
        status = process_form(self.add_form, DebitCard)
        return self.redirects[status]

    def edit(self):
        status = process_form(
            self.edit_form, DebitCard, alt_update=DebitCard.remove_from_project
        )
        return self.redirects[status]

    def get_forms(self):
        forms: List[EditDebitCardForm] = []
        for debit_card in DebitCard.query.filter_by(project_id=self.project.id):
            forms.append(
                EditDebitCardForm(prefix="edit_debit_card_form", **debit_card.__dict__)
            )
            self.debit_card_numbers.append(debit_card.card_number)
            self.debit_cards.append(debit_card)
        # Not inserting the form with an error because this shouldn't be able to happen.
        # See FunderController on how it should actually be done.
        return forms

    def process_forms(self):
        redirect = self.add()
        if redirect:
            return redirect
        redirect = self.edit()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        # Not implemented for EditDebitCardForm. Errors shouldn't be able to happen.
        if len(self.add_form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#project-beheren", "#betaalpas-toevoegen"])
        return modals

    def get_donuts(self):
        return [
            {
                **calculate_amounts(
                    DebitCard,
                    x.id,
                    db.session.query(Payment)
                    .join(DebitCard)
                    .filter(DebitCard.id == x.id)
                    .all(),
                ),
                "card_number": x.card_number,
            }
            for x in self.debit_cards
        ]
