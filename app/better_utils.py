import os


def format_flash(text, color):
    return f"<span class=text-default-{color}>{text}</span>"


def get_thumbnail_paths(project):
    # TODO: Refactor this in combination with save_attachment.
    return [
        os.path.splitext(attachment.filename)[0] + "_thumb.jpeg"
        for attachment in project.get_all_attachments()
        if attachment.mimetype in ["image/jpeg", "image/jpg", "image/png"]
    ]

    # import logging
    # logger = logging.getLogger("weasyprint")
    # logger.handlers = []  # Remove the default stderr handler
    # logger.addHandler(logging.FileHandler("./weasyprint.log"))
