from pdfkit import from_string
from flask import render_template
from app.models import Project


def create_pdf():
    project = Project.query.get(28)

    rendered_template = render_template(
        "justification-rapport.html",
        title="Titel",
        subtitle="Subtitel",
        project=project,
    )

    file_content = from_string(
        rendered_template,
        css="./app/assets/styles/justification_rapport.css",
    )

    return file_content


def save_pdf(file_content):
    with open("testrapportage-openpoen.pdf", "wb+") as file:
        file.write(file_content)


def test():
    pdf_file = create_pdf()
    save_pdf(pdf_file)
