from app.controllers.util import Controller, create_redirects
from app.forms import EditProjectForm
from app.models import Project
from app.form_processing import process_form


class ProjectController(Controller):
    def __init__(self, project: Project):
        self.project = project
        self.form = EditProjectForm(prefix="project_form")
        # Because it's not allowed to change this property after instantiation.
        self.form.contains_subprojects.data = project.contains_subprojects
        self.redirects = create_redirects(self.project.id, None)

    def process(self):
        status = process_form(self.form, Project)
        return self.redirects[status]

    def get_forms(self):
        if len(self.form.errors) > 0:
            form = self.form
        else:
            form = EditProjectForm(prefix="project_form", **self.project.__dict__)
        # Make the user unable to change this property in the UI.
        form.contains_subprojects.render_kw = {"disabled": ""}
        return form

    def process_forms(self):
        redirect = self.process()
        if redirect:
            return redirect

    def get_modal_ids(self, modals):
        if len(self.form.errors) > 0:
            assert len(modals) == 0
            modals.extend(["#project-beheren"])
        return modals
