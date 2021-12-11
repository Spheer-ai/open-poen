from app import app
from app.models import User, Payment
from flask import url_for
from pprint import pprint
import click
from app import util


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
@click.option('-e', '--email', required=True)
@click.option('-a', '--admin', is_flag=True)
@click.option('-pid', '--project_id', type=int)
@click.option('-sid', '--subproject_id', type=int)
def add_user(email, admin=False,
             project_id=0, subproject_id=0):
    """
    Adds a user. This command will prompt for an email address and
    allows the user to be added as admin or linked to a (sub)project. If
    it does not exist yet a user will be created.
    """
    util.add_user(email, admin, project_id, subproject_id)
    print("Added user")


@database.command()
@click.argument('email')
def create_user_invite_link(email):
    """
    Create a 'reset password' URL for a user. Useful to avoid emails
    in the process of resetting a users password. Provide the users
    email address as parameter.
    """
    user = User.query.filter_by(email=email).first()
    if not user:
        print('No user with email address %s' % (email))
        return
    token = user.get_reset_password_token()
    print(
        'Password reset URL for %s: %s' % (
            email,
            url_for('reset_wachtwoord', token=token, _external=True)
        )
    )
