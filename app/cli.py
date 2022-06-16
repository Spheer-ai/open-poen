from app import app
from app.populate import populate_db_with_test_data, add_subprojects, delete_test_data
from app.models import User, Payment
from flask import url_for
from pprint import pprint
import click
from app.bng import get_bng_payments
from sqlalchemy.exc import IntegrityError
import os
from PIL import Image


@app.cli.group()
def bng():
    """BNG related commands"""
    pass


@bng.command()
def get_new_payments_all():
    """Get all payments from the coupled BNG account"""
    try:
        get_bng_payments()
        app.logger.info("Succesfully retrieved payments from BNG.")
    except (NotImplementedError, ValueError, IntegrityError, ConnectionError) as e:
        app.logger.error(repr(e) + "\n" + "Failed to retrieve payments from BNG.")
        return


# Database commands
@app.cli.group()
def database():
    """Open Poen database related commands"""
    pass


@database.command()
def show_all_users():
    """
    Show all Open Poen users
    """
    for user in User.query.all():
        pprint(vars(user))


@database.command()
def show_all_payments():
    """
    Show all payments
    """
    for payment in Payment.query.all():
        pprint(vars(payment))


@database.command()
@click.option("-e", "--email", required=True)
@click.option("-a", "--admin", is_flag=True)
@click.option("-pid", "--project_id", type=int)
@click.option("-sid", "--subproject_id", type=int)
def add_user(email, admin=False, project_id=0, subproject_id=0):
    """
    Adds a user. This command will prompt for an email address and
    allows the user to be added as admin or linked to a (sub)project. If
    it does not exist yet a user will be created.
    """
    User.add_user(email, admin, project_id, subproject_id)
    print("Added user")


@database.command()
@click.argument("email")
def create_user_invite_link(email):
    """
    Create a 'reset password' URL for a user. Useful to avoid emails
    in the process of resetting a users password. Provide the users
    email address as parameter.
    """
    user = User.query.filter_by(email=email).first()
    if not user:
        print("No user with email address %s" % (email))
        return
    token = user.get_reset_password_token()
    print(
        "Password reset URL for %s: %s"
        % (email, url_for("reset_wachtwoord", token=token, _external=True))
    )


@database.command()
@click.option("-s", "--subprojects", required=True)
def populate(subprojects):
    """Populates the database with a couple of "fake" test projects.
    Useful for testing.
    """
    populate_db_with_test_data()
    if subprojects:
        add_subprojects()


@database.command()
def delete():
    """Deletes the test project."""
    delete_test_data()


@database.command()
def generate_thumbnails():
    folder = os.path.join(
        os.path.split(app.instance_path)[0],
        app.config["UPLOAD_FOLDER"],
        "transaction-attachment",
    )
    for attachment in os.listdir(folder):
        if not attachment.endswith(("jpg", "jpeg", "png")) or "thumb" in attachment:
            continue
        im = Image.open(os.path.join(folder, attachment))
        im = im.convert("RGB")
        im.thumbnail((320, 320), Image.ANTIALIAS)
        thumbnail_filename = os.path.splitext(attachment)[0] + "_thumb.jpeg"
        im.save(os.path.join(folder, thumbnail_filename), "JPEG")
        print(f"Created {thumbnail_filename}.")
