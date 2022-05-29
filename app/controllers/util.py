import re
from abc import ABCMeta, abstractmethod
from typing import Dict, List, Union
from app import app
from app.form_processing import Status, return_redirect
from flask import Response, request
from flask.templating import render_template
from flask_wtf import FlaskForm


class Controller(metaclass=ABCMeta):
    @property
    def get_id_of_submitted_form(self):
        keys = list(request.form.keys())
        if len(keys) > 0:
            try:
                id = int(re.search("\d+", keys[0]).group(0))
            except (IndexError, AttributeError):
                id = None
            return id
        else:
            return None

    @abstractmethod
    def get_forms(self) -> Union[FlaskForm, List[FlaskForm]]:
        pass

    @abstractmethod
    def process_forms(self) -> Union[None, Response]:
        pass

    @abstractmethod
    def get_modal_ids(self, modals: List[str]) -> List[str]:
        pass

    @staticmethod
    def check_clearance(func):
        # TODO: This messes up any redirect that func returns somehow.
        def check(self, form):
            if self.clearance >= form.clearance:
                func(self, form)

        return check


def redirects_from_keys(
    response: Response,
) -> Dict[Union[None, Status], Union[None, Response]]:
    redirects = dict.fromkeys(
        [
            Status.succesful_delete,
            Status.succesful_edit,
            Status.failed_edit,
            Status.succesful_create,
            Status.failed_create,
        ],
        response,
    )
    redirects[Status.not_found] = render_template("404.html")
    redirects[None] = None
    return redirects


def create_redirects_for_project_or_subproject(
    project_id: int, subproject_id: Union[None, int]
) -> Dict[Union[None, Status], Union[None, Response]]:
    return redirects_from_keys(return_redirect(project_id, subproject_id))


def create_redirects_for_response(
    response: Response,
) -> Dict[Union[None, Status], Union[None, Response]]:
    return redirects_from_keys(response)
