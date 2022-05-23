from typing import Dict

from app.controllers.util import Controller, create_redirects_for_project_or_subproject
from app.form_processing import process_form, BaseHandler, Status
from app.forms import (
    EditAttachmentForm,
    TransactionAttachmentForm,
)
from app.models import Project, File
from flask import flash


class AttachmentFormHandler(BaseHandler):
    def on_create(self) -> Status:
        instance = File.add_attachment(**self.data)
        flash(instance.on_succesful_create)
        return Status.succesful_create


class AttachmentController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.add_form = TransactionAttachmentForm(prefix="transaction_attachment_form")
        self.edit_form = EditAttachmentForm(
            prefix=f"edit_attachment_form_{self.get_id_of_submitted_form}"
        )
        self.redirects = create_redirects_for_project_or_subproject(
            self.project.id, None
        )

    def add(self):
        status = process_form(AttachmentFormHandler(self.add_form, File))
        return self.redirects[status]

    def edit(self):
        status = process_form(AttachmentFormHandler(self.edit_form, File))
        return self.redirects[status]

    def get_forms(self):
        forms: Dict[int, EditAttachmentForm] = {}
        # TODO: Make sure only the attachments for the user's permissions are returned.
        # AKA: Editable payments.
        for attachment in self.project.get_all_attachments():
            data = attachment.__dict__
            id = data["id"]
            form = EditAttachmentForm(prefix=f"edit_attachment_form_{id}", **data)
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
        pass
