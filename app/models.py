from ast import Assert
import locale
from datetime import datetime
from os import urandom
from time import time

import jwt
from flask_login import UserMixin
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app import app, db, login_manager
from app.email import send_invite

# Association table between Project and User
project_user = db.Table(
    "project_user",
    db.Column(
        "project_id", db.Integer, db.ForeignKey("project.id", ondelete="CASCADE")
    ),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("project_id", "user_id"),
)


# Association table between Subproject and User
subproject_user = db.Table(
    "subproject_user",
    db.Column(
        "subproject_id", db.Integer, db.ForeignKey("subproject.id", ondelete="CASCADE")
    ),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("subproject_id", "user_id"),
)


# Association table between Payment and File for attachments
payment_attachment = db.Table(
    "payment_attachment",
    db.Column(
        "payment_id", db.Integer, db.ForeignKey("payment.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("payment_id", "file_id"),
)


# Assocation table between Project and File for images
project_image = db.Table(
    "project_image",
    db.Column(
        "project_id", db.Integer, db.ForeignKey("project.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("project_id", "file_id"),
)


# Assocation table between Subproject and File for images
subproject_image = db.Table(
    "subproject_image",
    db.Column(
        "subproject_id", db.Integer, db.ForeignKey("subproject.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("subproject_id", "file_id"),
)


# Assocation table between Funder and File for images
funder_image = db.Table(
    "funder_image",
    db.Column("funder_id", db.Integer, db.ForeignKey("funder.id", ondelete="CASCADE")),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("funder_id", "file_id"),
)


# Assocation table between UserStory and File for images
user_story_image = db.Table(
    "userstory_image",
    db.Column(
        "user_story_id", db.Integer, db.ForeignKey("user_story.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("user_story_id", "file_id"),
)


class DefaultCRUD(object):
    def update(self, data):
        for key, value in data.items():
            setattr(self, key, value)
        db.session.commit()

    @classmethod
    def create(cls, data):
        instance = cls(**data)
        db.session.add(instance)
        db.session.commit()
        return instance


class BNGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    consent_id = db.Column(db.String(36))
    access_token = db.Column(db.String(2048))
    expires_on = db.Column(db.DateTime())
    last_import_on = db.Column(db.DateTime())
    iban = db.Column(db.String(34), unique=True)


class User(UserMixin, db.Model, DefaultCRUD):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(120), index=True)
    last_name = db.Column(db.String(120), index=True)
    biography = db.Column(db.String(1000))
    hidden = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    image = db.Column(db.Integer, db.ForeignKey("file.id", ondelete="SET NULL"))

    def is_active(self):
        return self.active

    def set_password(self, password):
        if len(password) < 12:
            raise RuntimeError(
                "Attempted to set password with length less than 12 characters"
            )
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=86400):
        return jwt.encode(
            {"reset_password": self.id, "exp": time() + expires_in},
            app.config["SECRET_KEY"],
            algorithm="HS256",
        ).decode("utf-8")

    @staticmethod
    def verify_reset_password_token(token):
        try:
            user_id = jwt.decode(token, app.config["SECRET_KEY"], algorithms="HS256")[
                "reset_password"
            ]
        except:
            return
        return User.query.get(user_id)

    def __repr__(self):
        return "<User {}>".format(self.email)

    def edit_project_owner(self, remove_from_project, **kwargs):
        if remove_from_project:
            self.projects.remove(Project.query.get(kwargs["project_id"]))
            db.session.commit()
        else:
            del kwargs["remove_from_project"]
            del kwargs["project_id"]
            return super(User, self).update(kwargs)

    def edit_subproject_owner(self, remove_from_subproject, **kwargs):
        if remove_from_subproject:
            self.subprojects.remove(Subproject.query.get(kwargs["subproject_id"]))
            db.session.commit()
        else:
            del kwargs["remove_from_subproject"]
            del kwargs["subproject_id"]
            return super(User, self).update(kwargs)

    @classmethod
    def add_user(cls, email, admin=False, project_id=0, subproject_id=0):
        user = cls.query.filter_by(email=email).first()

        if user:
            _set_user_role(user, admin, project_id, subproject_id)
        if not user:
            user = cls(email=email)
            user.set_password(urandom(24))
            db.session.add(user)
            db.session.commit()
            _set_user_role(user, admin, project_id, subproject_id)
            send_invite(user)

        return user

    @property
    def message_after_edit(self):
        return f"Gebruiker {self.email} is aangepast."

    @property
    def message_after_create(self):
        return f"Gebruiker {self.email} is aangemaakt."

    @property
    def message_after_delete(self):
        return f"Gebruiker {self.email} is verwijderd."

    def message_after_edit_error(self, error, data):
        return "Aanpassen mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."

    @classmethod
    def message_after_create_error(cls, error, data):
        if type(error) == ValueError:
            return str(error)
        else:
            return "Aanmaken mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."


class Project(db.Model, DefaultCRUD):
    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(64), index=True)
    # This has to become a BNG token.
    bunq_access_token = db.Column(db.String(64))
    # This needs to be removed, or needs to become something linked to BNG.
    iban = db.Column(db.String(34), index=True, unique=True)
    iban_name = db.Column(db.String(120), index=True)
    name = db.Column(db.String(120), index=True, unique=True)
    description = db.Column(db.Text)
    contains_subprojects = db.Column(db.Boolean, default=True)
    hidden = db.Column(db.Boolean, default=False)
    hidden_sponsors = db.Column(db.Boolean, default=False)
    budget = db.Column(db.Integer)

    subprojects = db.relationship(
        "Subproject",
        backref="project",
        lazy="dynamic",
        order_by="Subproject.name.asc()",
        cascade="all,delete,delete-orphan",
    )
    users = db.relationship(
        "User", secondary=project_user, backref="projects", lazy="dynamic"
    )
    funders = db.relationship("Funder", backref="project", lazy="dynamic")
    # This has to become passes I guess.
    ibans = db.relationship("IBAN", backref="project", lazy="dynamic")
    payments = db.relationship(
        "Payment",
        backref="project",
        lazy="dynamic",
        order_by="Payment.transaction_id.desc()",
    )
    images = db.relationship("File", secondary=project_image, lazy="dynamic")
    categories = db.relationship("Category", backref="project", lazy="dynamic")
    debit_cards = db.relationship("DebitCard", backref="project", lazy="dynamic")

    def set_bank_name(self, bank_name):
        self.bank_name = bank_name

    # Returns true if the project is linked to the given user_id
    def has_user(self, user_id):
        return self.users.filter(project_user.c.user_id == user_id).count() > 0

    # Create category select options to be shown in a dropdown menu
    def make_category_select_options(self):
        select_options = [("", "Geen")]
        for category in Category.query.filter_by(project_id=self.id):
            select_options.append((str(category.id), category.name))
        return select_options

    def make_subproject_select_options(self):
        select_options = [("", "Hoofdactiviteit")]
        for subproject in self.subprojects.all():
            select_options.append((str(subproject.id), subproject.name))
        return select_options

    def make_debit_card_select_options(self):
        select_options = []
        for debit_card in self.debit_cards.all():
            select_options.append((debit_card.card_number, debit_card.card_number))
        return select_options

    def get_all_payments(self):
        debit_card_payments = (
            db.session.query(Payment)
            .join(DebitCard)
            .join(Project)
            .filter(Project.id == self.id)
            .all()
        )
        subproject_payments = (
            db.session.query(Payment).join(Project).filter(Project.id == self.id).all()
        )
        return list(set(debit_card_payments + subproject_payments))

    @property
    def message_after_edit(self):
        return f"Initiatief {self.name} is aangepast."

    @property
    def message_after_create(self):
        return f"Initiatief {self.name} is aangemaakt."

    @property
    def message_after_delete(self):
        return f"Initiatief {self.name} is verwijderd."

    def message_after_edit_error(self, error, data):
        if type(error) == IntegrityError:
            return f"Aanpassen mislukt. De naam {data['name']} is al gebruikt voor een ander initiatief."
        else:
            return "Aanpassen mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."

    @classmethod
    def message_after_create_error(cls, error, data):
        if type(error) == IntegrityError:
            return f"Aanmaken mislukt. De naam {data['name']} is al gebruikt voor een ander initiatief."
        else:
            return "Aanmaken mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."


class Subproject(db.Model, DefaultCRUD):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"))
    # This needs to be removed, or needs to become something linked to BNG.
    iban = db.Column(db.String(34), index=True, unique=True)
    iban_name = db.Column(db.String(120), index=True)
    name = db.Column(db.String(120), index=True)
    description = db.Column(db.Text)
    hidden = db.Column(db.Boolean, default=False)
    budget = db.Column(db.Integer)

    users = db.relationship(
        "User", secondary=subproject_user, backref="subprojects", lazy="dynamic"
    )
    payments = db.relationship("Payment", backref="subproject", lazy="dynamic")
    images = db.relationship("File", secondary=subproject_image, lazy="dynamic")
    categories = db.relationship(
        "Category",
        backref="subproject",
        lazy="dynamic",
        cascade="all,delete,delete-orphan",
    )

    # Subproject names must be unique within a project
    __table_args__ = (db.UniqueConstraint("project_id", "name"),)

    # Returns true if the subproject is linked to the given user_id
    def has_user(self, user_id):
        return self.users.filter(subproject_user.c.user_id == user_id).count() > 0

    # Create select options to be shown in a dropdown menu
    def make_category_select_options(self):
        select_options = [("", "Geen")]
        for category in Category.query.filter_by(subproject_id=self.id):
            select_options.append((str(category.id), category.name))
        return select_options

    @property
    def message_after_edit(self):
        return f"Activiteit {self.name} is aangepast."

    @property
    def message_after_create(self):
        return f"Activiteit {self.name} is aangemaakt."

    @property
    def message_after_delete(self):
        return f"Activiteit {self.name} is verwijderd."

    def message_after_edit_error(self, error, data):
        if type(error) == IntegrityError:
            return f"Aanpassen mislukt. De naam {data['name']} is al gebruikt voor een andere activiteit in dit project."
        else:
            return "Aanpassen mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."

    @classmethod
    def message_after_create_error(cls, error, data):
        if type(error) == IntegrityError:
            return f"Aanmaken mislukt. De naam {data['name']} is al gebruikt voor een andere activiteit in dit project."
        else:
            return "Aanmaken mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."


def _set_user_role(user, admin=False, project_id=0, subproject_id=0):
    if admin:
        user.admin = True
        db.session.commit()
    if project_id:
        project = Project.query.get(project_id)
        if user in project.users:
            raise ValueError(
                "Gebruiker niet toegevoegd: deze gebruiker was al initiatiefnemer van dit initiatief."
            )
        project.users.append(user)
        db.session.commit()
    if subproject_id:
        subproject = Subproject.query.get(subproject_id)
        if user in subproject.users:
            raise ValueError(
                "Gebruiker niet toegevoegd: deze gebruiker was al activiteitnemer van deze activiteit."
            )
        subproject.users.append(user)
        db.session.commit()


# TODO: Use this for BNG.
class DebitCard(db.Model, DefaultCRUD):
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.String(22), unique=True, nullable=False)
    payments = db.relationship("Payment", backref="debit_card", lazy="dynamic")
    project_id = db.Column(db.ForeignKey("project.id", ondelete="SET NULL"))
    last_used_project_id = db.Column(db.Integer)

    @property
    def message_after_edit(self):
        return f"Betaalpas {self.card_number} is ontkoppeld."

    @property
    def message_after_create(self):
        return f"Betaalpas {self.card_number} is toegevoegd."

    @classmethod
    def create(cls, data):
        present_debit_card = cls.query.filter_by(
            card_number=data["card_number"]
        ).first()
        if present_debit_card:
            present_debit_card.update(data)
            return present_debit_card
        else:
            return super(DebitCard, cls).create(data)

    def remove_from_project(self, remove_from_project, **kwargs):
        if remove_from_project:
            payments = (
                db.session.query(Payment)
                .join(DebitCard)
                .filter(DebitCard.id == self.id)
                .all()
            )
            if len(payments) > 0:
                raise ValueError(
                    "Payments have already been done with this debit card."
                )
            self.last_used_project_id = self.project_id
            del self.project
            db.session.commit()

    def message_after_edit_error(self, error, data):
        if type(error) == ValueError:
            return (
                "Betaalpas verwijderen is mislukt. Een betaalpas mag alleen worden verwijderd, als er "
                "nog geen betalingen mee zijn gedaan."
            )
        else:
            return "Aanpassen mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."

    @classmethod
    def message_after_create_error(cls, error, data):
        if type(error) == ValueError:
            return (
                "Betaalpas verwijderen is mislukt. Een betaalpas mag alleen worden verwijderd, als er "
                "nog geen betalingen mee zijn gedaan."
            )
        else:
            return "Aanmaken mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."


# TODO: Make this compatible with BNG payments if necessary.
class Payment(db.Model, DefaultCRUD):
    subproject_id = db.Column(
        db.Integer, db.ForeignKey("subproject.id", ondelete="SET NULL")
    )
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="SET NULL"))
    category_id = db.Column(
        db.Integer, db.ForeignKey("category.id", ondelete="SET NULL")
    )

    # Fields coming from the BNG API (Snake case conversion is done by us.)
    # 'transaction_id':'79afd730-950e-4b9e-8fbb-fa643e4d0fbb'
    # 'entry_reference':'Bank reference 5532530633'
    # 'end_to_end_id':'42e272ca60144a32842cd72d134a881c'
    # 'booking_date':datetime.datetime(2021, 12, 18, 0, 0)
    # 'transaction_amount_currency':'EUR'
    # 'transaction_amount_amount':-10.0
    # 'creditor_name':'Other account'
    # 'creditor_account_iban':'NL92NEMO94126583559281'
    # 'creditor_account_currency':'EUR'
    # 'debtor_name':''
    # 'remittance_information_unstructured':'Description'
    # 'remittance_information_structured':'/TRTP/Vertaling Bookcode/REMI/Additionele gegevens'

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(64), unique=True)
    entry_reference = db.Column(db.String(32))
    end_to_end_id = db.Column(db.String(32))
    booking_date = db.Column(db.DateTime(timezone=True))
    created = db.Column(db.DateTime(timezone=True), default=datetime.now)
    updated = db.Column(db.DateTime(timezone=True), onupdate=datetime.now)
    transaction_amount = db.Column(db.Float())
    creditor_name = db.Column(db.String(128))
    creditor_account = db.Column(db.String(22))
    debtor_name = db.Column(db.String(128))
    debtor_account = db.Column(db.String(22))
    remittance_information_unstructured = db.Column(db.Text())
    remittance_information_structured = db.Column(db.Text())
    # Can be 'inbesteding', 'uitgaven' or 'inkomsten'
    route = db.Column(db.String(12))
    card_number = db.Column(db.String(22), db.ForeignKey("debit_card.card_number"))
    type = db.Column(db.String(20))

    # Fields coming from the user
    short_user_description = db.Column(db.String(50))
    long_user_description = db.Column(db.String(1000))
    hidden = db.Column(db.Boolean, default=False)

    attachments = db.relationship("File", secondary=payment_attachment, lazy="dynamic")

    def get_formatted_currency(self):
        return locale.format(
            "%.2f", self.transaction_amount, grouping=True, monetary=True
        )

    def get_export_currency(self):
        return self.get_formatted_currency().replace("\u202f", "")

    def make_category_select_options(self):
        # TODO: Refactor.
        if self.subproject:
            return self.subproject.make_category_select_options()
        elif self.project:
            return self.project.make_category_select_options()
        elif self.debit_card:
            return self.debit_card.project.make_category_select_options()
        else:
            raise AssertionError("Edge case: can't find this payment's project.")

    def make_subproject_select_options(self):
        # TODO: Refactor.
        if self.subproject:
            return self.subproject.project.make_subproject_select_options()
        elif self.project and self.project.contains_subprojects:
            return self.project.make_subproject_select_options()
        elif self.debit_card and self.debit_card.project.contains_subprojects:
            return self.debit_card.project.make_subproject_select_options()
        else:
            raise AssertionError("Edge case: can't find this payment's project.")

    @classmethod
    def add_manual_topup_or_payment(cls, transaction_amount, **kwargs):
        if transaction_amount > 0:
            kwargs["route"] = "inkomsten"
        elif transaction_amount <= 0:
            kwargs["route"] = "uitgaven"
        kwargs["transaction_amount"] = transaction_amount
        return super(Payment, cls).create(kwargs)

    @property
    def message_after_edit(self):
        return "Betaling is aangepast."

    @property
    def message_after_create(self):
        return "Betaling is aangemaakt."

    @property
    def message_after_delete(self):
        return "Betaling is verwijderd."

    def message_after_edit_error(self, error, data):
        return "Aanpassen mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."

    @classmethod
    def message_after_create_error(cls, error, data):
        return "Aanmaken mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."


class Funder(db.Model, DefaultCRUD):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"))
    name = db.Column(db.String(120), index=True)
    url = db.Column(db.String(2000))
    images = db.relationship("File", secondary=funder_image, lazy="dynamic")

    @property
    def message_after_edit(self):
        return f"Sponsor {self.name} is aangepast."

    @property
    def message_after_create(self):
        return f"Sponsor {self.name} is aangemaakt."

    @property
    def message_after_delete(self):
        return f"Sponsor {self.name} is verwijderd."

    def message_after_edit_error(self, error, data):
        return "Aanpassen mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."

    @classmethod
    def message_after_create_error(cls, error, data):
        return "Aanmaken mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."


# Make these BNG accounts?
class IBAN(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"))
    iban = db.Column(db.String(34), index=True)


class UserStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(240), index=True)
    title = db.Column(db.String(200))
    text = db.Column(db.String(200))
    hidden = db.Column(db.Boolean, default=False)
    images = db.relationship("File", secondary=user_story_image, lazy="dynamic")


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), index=True)
    mimetype = db.Column(db.String(255))
    mediatype = db.Column(db.String(32))


class Category(db.Model, DefaultCRUD):
    id = db.Column(db.Integer, primary_key=True)
    subproject_id = db.Column(
        db.Integer, db.ForeignKey("subproject.id", ondelete="CASCADE")
    )
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"))
    name = db.Column(db.String(120), index=True)
    payments = db.relationship("Payment", backref="category", lazy="dynamic")

    # Category names must be unique within a (sub)project
    __table_args__ = (db.UniqueConstraint("project_id", "subproject_id", "name"),)

    @property
    def message_after_edit(self):
        return f"Categorie {self.name} is aangepast."

    @property
    def message_after_create(self):
        return f"Categorie {self.name} is aangemaakt."

    @property
    def message_after_delete(self):
        return f"Categorie {self.name} is verwijderd."

    def message_after_edit_error(self, error, data):
        return "Aanpassen mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."

    @classmethod
    def message_after_create_error(cls, error, data):
        # TODO: Add error for duplicate name. Integrity error.
        return "Aanmaken mislukt vanwege een onbekende fout. De beheerder van Open Poen is op de hoogte gesteld."


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
