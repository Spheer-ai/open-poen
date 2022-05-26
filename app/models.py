import locale
import os
from datetime import datetime
from os import urandom
from time import time
from typing import Dict, List, Tuple

import jwt
from flask_login import UserMixin
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import app.exceptions as ex
from app import app, db, login_manager
from app.better_utils import format_flash
from app.email import send_invite
from PIL import Image


def format_currency_with_cents(amount):
    return locale.format("%.2f", amount, grouping=True, monetary=True)


class DefaultCRUD(object):
    def update(self, data: Dict):
        for key, value in data.items():
            setattr(self, key, value)
        db.session.commit()

    @classmethod
    def create(cls, data: Dict):
        instance = cls(**data)
        db.session.add(instance)
        db.session.commit()
        return instance


class DefaultErrorMessages:
    @property
    def on_succesful_edit(self) -> str:
        return format_flash(f"{self.error_info} is aangepast.", "green")

    @property
    def on_failed_edit(self) -> str:
        return format_flash(f"{self.error_info} is niet aangepast.", "red")

    @property
    def on_succesful_create(self) -> str:
        return format_flash(f"{self.error_info} is aangemaakt.", "green")

    @property
    def on_failed_create(self) -> str:
        return format_flash(f"{self.error_info} is niet aangemaakt.", "red")

    @property
    def on_succesful_delete(self) -> str:
        """No need for a "on_failed_delete", because in that case, a 404 page is
        returned."""
        return format_flash(f"{self.error_info} is verwijderd.", "green")

    @property
    def error_info(self):
        return "Object"


project_user = db.Table(
    "project_user",
    db.Column(
        "project_id", db.Integer, db.ForeignKey("project.id", ondelete="CASCADE")
    ),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("project_id", "user_id"),
)


subproject_user = db.Table(
    "subproject_user",
    db.Column(
        "subproject_id", db.Integer, db.ForeignKey("subproject.id", ondelete="CASCADE")
    ),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("subproject_id", "user_id"),
)

subproject_funder = db.Table(
    "subproject_funder",
    db.Column(
        "subproject_id", db.Integer, db.ForeignKey("subproject.id", ondelete="CASCADE")
    ),
    db.Column("funder_id", db.Integer, db.ForeignKey("funder.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("subproject_id", "funder_id"),
)


payment_attachment = db.Table(
    "payment_attachment",
    db.Column(
        "payment_id", db.Integer, db.ForeignKey("payment.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("payment_id", "file_id"),
)


project_image = db.Table(
    "project_image",
    db.Column(
        "project_id", db.Integer, db.ForeignKey("project.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("project_id", "file_id"),
)


subproject_image = db.Table(
    "subproject_image",
    db.Column(
        "subproject_id", db.Integer, db.ForeignKey("subproject.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("subproject_id", "file_id"),
)


funder_image = db.Table(
    "funder_image",
    db.Column("funder_id", db.Integer, db.ForeignKey("funder.id", ondelete="CASCADE")),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("funder_id", "file_id"),
)


user_story_image = db.Table(
    "userstory_image",
    db.Column(
        "user_story_id", db.Integer, db.ForeignKey("user_story.id", ondelete="CASCADE")
    ),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id", ondelete="CASCADE")),
    db.PrimaryKeyConstraint("user_story_id", "file_id"),
)


class BNGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    consent_id = db.Column(db.String(36))
    access_token = db.Column(db.String(2048))
    expires_on = db.Column(db.DateTime())
    last_import_on = db.Column(db.DateTime())
    iban = db.Column(db.String(34), unique=True)


class User(UserMixin, db.Model, DefaultCRUD, DefaultErrorMessages):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    financial = db.Column(db.Boolean, default=False)
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
            del kwargs["project_id"]
            return super(User, self).update(kwargs)

    def edit_subproject_owner(self, remove_from_subproject, **kwargs):
        if remove_from_subproject:
            self.subprojects.remove(Subproject.query.get(kwargs["subproject_id"]))
            db.session.commit()
        else:
            del kwargs["subproject_id"]
            return super(User, self).update(kwargs)

    @classmethod
    def add_user(
        cls,
        email,
        admin=False,
        financial=False,
        project_id=0,
        subproject_id=0,
        **kwargs,
    ):
        user = cls.query.filter_by(email=email).first()

        if user:
            user._set_user_role(admin, financial, project_id, subproject_id)
            db.session.commit()
        if not user:
            user = cls(email=email)
            user.set_password(urandom(24))
            db.session.add(user)
            user._set_user_role(admin, financial, project_id, subproject_id)
            db.session.commit()
            send_invite(user)

        return user

    def _set_user_role(
        self, admin=False, financial=False, project_id=0, subproject_id=0
    ):
        if admin:
            self.admin = True
        if financial:
            self.financial = True
        if project_id:
            project = Project.query.get(project_id)
            if self in project.users:
                raise ex.UserIsAlreadyPresentInProject(self.email)
            project.users.append(self)
        if subproject_id:
            subproject = Subproject.query.get(subproject_id)
            if self in subproject.users:
                raise ex.UserIsAlreadyPresentInSubproject(self.email)
            subproject.users.append(self)

    @property
    def error_info(self):
        return f"Gebruiker '{self.email}'"


class Project(db.Model, DefaultCRUD, DefaultErrorMessages):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), index=True, unique=True)
    description = db.Column(db.Text)
    purpose = db.Column(db.Text)
    target_audience = db.Column(db.Text)
    contains_subprojects = db.Column(db.Boolean, default=True)
    hidden = db.Column(db.Boolean, default=False)
    hidden_sponsors = db.Column(db.Boolean, default=False)
    owner = db.Column(db.String(120))
    owner_email = db.Column(db.String(120))
    legal_entity = db.Column(db.String(20))
    address_applicant = db.Column(db.String(120))
    registration_kvk = db.Column(db.String(120))
    project_location = db.Column(db.String(120))
    # TODO: budget_file
    budget = db.Column(db.Integer)
    image = db.Column(db.Integer, db.ForeignKey("file.id", ondelete="SET NULL"))

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
    payments = db.relationship(
        "Payment",
        backref="project",
        lazy="dynamic",
        order_by="Payment.transaction_id.desc()",
    )
    images = db.relationship("File", secondary=project_image, lazy="dynamic")
    categories = db.relationship("Category", backref="project", lazy="dynamic")
    debit_cards = db.relationship("DebitCard", backref="project", lazy="dynamic")

    def __repr__(self):
        return "<Project {}>".format(self.name)

    def has_user(self, user_id):
        return self.users.filter(project_user.c.user_id == user_id).count() > 0

    def make_category_select_options(self):
        select_options = [("", "Geen")]
        for category in self.categories.all():
            select_options.append((str(category.id), category.name))
        return select_options

    def make_subproject_select_options(self, user_id=None):
        select_options = [("", "Hoofdactiviteit")]
        for subproject in self.subprojects.all():
            if user_id is not None and not subproject.has_user(user_id):
                continue
            if subproject.finished:
                continue
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
        # As of now, all manual payments either have a project id, or a project id and
        # a subproject id. Never only a subproject id.
        other_payments = (
            db.session.query(Payment).join(Project).filter(Project.id == self.id).all()
        )
        return list(set(debit_card_payments + other_payments))

    @property
    def get_payments_without_subproject(self):
        return [x for x in self.get_all_payments() if x.subproject_id is None]

    def get_all_attachments(self):
        all_payments = self.get_all_payments()

        return (
            db.session.query(File)
            .join(payment_attachment)
            .join(Payment)
            .filter(Payment.id.in_([x.id for x in all_payments]))
            .all()
        )

    @classmethod
    def add_project(cls, card_numbers, funders, project_owners, budget_file, **kwargs):

        project = cls(**kwargs)

        # Check that ensures the debit card is not already linked to a different project,
        # is done in the form validator.
        existing = (  # Existing debit cards that are not linked to a project yet.
            db.session.query(DebitCard)
            .filter(DebitCard.card_number.in_([x["card_number"] for x in card_numbers]))
            .all()
        )
        new = [  # New debit cards that are not in the database yet.
            DebitCard(**x)
            for x in card_numbers
            if x["card_number"] not in [i.card_number for i in existing]
        ]
        project.debit_cards = existing + new

        project.funders = [Funder(**x) for x in funders]

        db.session.add(project)
        try:
            db.session.commit()
        except IntegrityError as e:
            app.logger.info(repr(e))
            raise ex.DuplicateProjectName(kwargs["name"])

        for project_owner in project_owners:
            User.add_user(project_owner["email"], project_id=project.id)

        return project

    def justify(self, funder, concept, send, **kwargs):
        funder = Funder.query.get(funder)
        if concept:
            # TODO: Download the PDF-rapport.
            pass
        elif send:
            funder.justified = True
            db.session.add(funder)
            db.session.commit()
            # TODO: Send the PDF-rapport.
        return self

    def concept_justify(self, funder, concept, send, **kwargs):
        funder = Funder.query.get(funder)
        if concept:
            # TODO: Download the PDF-rapport.
            pass
        elif send:
            # TODO: Send the PDF-rapport.
            pass
        return self

    @property
    def error_info(self):
        return f"Initiatief '{self.name}'"

    @property
    def unfinished_subprojects(self):
        return [x for x in self.subprojects.all() if not x.finished]

    @property
    def finished_subprojects(self):
        return [x for x in self.subprojects.all() if x.finished and not x.justified]

    @property
    def justified_subprojects(self):
        return [x for x in self.subprojects.all() if x.finished and x.justified]

    @property
    def coupleable_funders(self):
        return [x for x in self.funders if not x.justified]

    @property
    def formatted_budget(self):
        return "%s%s" % (
            "€ ",
            locale.format("%d", self.budget, grouping=True, monetary=True),
        )

    @property
    def financial_summary(self):
        return financial_summary(self.get_all_payments())


class Subproject(db.Model, DefaultCRUD, DefaultErrorMessages):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"))
    name = db.Column(db.String(120), index=True)
    description = db.Column(db.Text)
    purpose = db.Column(db.Text)
    target_audience = db.Column(db.Text)
    hidden = db.Column(db.Boolean, default=False)
    budget = db.Column(db.Integer)
    image = db.Column(db.Integer, db.ForeignKey("file.id", ondelete="SET NULL"))
    finished_description = db.Column(db.Text)
    finished = db.Column(db.Boolean, default=False)

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
    funders = db.relationship(
        "Funder",
        secondary=subproject_funder,
        lazy="dynamic",
        back_populates="subprojects",
    )

    # Subproject names must be unique within a project
    __table_args__ = (db.UniqueConstraint("project_id", "name"),)

    def has_user(self, user_id):
        return self.users.filter(subproject_user.c.user_id == user_id).count() > 0

    def make_category_select_options(self):
        select_options = [("", "Geen")]
        for category in Category.query.filter_by(subproject_id=self.id):
            select_options.append((str(category.id), category.name))
        return select_options

    def get_all_attachments(self):
        return (
            db.session.query(File)
            .join(payment_attachment)
            .join(Payment)
            .join(Subproject)
            .filter(Subproject.id == self.id)
            .all()
        )

    def update(self, data):
        try:
            super(Subproject, self).update(data)
        except IntegrityError as e:
            app.logger.info(repr(e))
            raise ex.DoubleSubprojectName(data["name"])

    @classmethod
    def create(cls, data):
        try:
            return super(Subproject, cls).create(data)
        except IntegrityError as e:
            app.logger.info(repr(e))
            raise ex.DoubleSubprojectName(data["name"])

    @property
    def error_info(self):
        return f"Activiteit '{self.name}'"

    @property
    def justified(self):
        return any([x.justified for x in self.funders.all()])

    @property
    def has_at_least_one_payment(self):
        return len(self.payments.all()) > 0

    @property
    def format_status(self):
        if self.justified:
            return "verantwoord"
        elif self.finished:
            return "afgerond"
        else:
            return "lopend"

    @property
    def formatted_budget(self):
        return "%s%s" % (
            "€ ",
            locale.format("%d", self.budget, grouping=True, monetary=True),
        )

    @property
    def financial_summary(self):
        return financial_summary(self.payments.all())


class DebitCard(db.Model, DefaultCRUD, DefaultErrorMessages):
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.String(22), unique=True, nullable=False)
    payments = db.relationship("Payment", backref="debit_card", lazy="dynamic")
    project_id = db.Column(db.ForeignKey("project.id", ondelete="SET NULL"))
    last_used_project_id = db.Column(db.Integer)

    @classmethod
    def create(cls, data):
        # TODO: The debit card form already checks that the debit card is not already
        # assigned to a different project, but it would be better to check for that
        # here, because of race conditions.
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
                raise ex.CoupledDebitCardHasPayments(self.card_number)
            self.last_used_project_id = self.project_id
            del self.project
            db.session.commit()

    @property
    def error_info(self):
        return f"Betaalpas '{self.card_number}'"


class Payment(db.Model, DefaultCRUD, DefaultErrorMessages):
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
        return format_currency_with_cents(self.transaction_amount)

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

    def make_subproject_select_options(self, user_id=None):
        # TODO: Refactor.
        if self.subproject:
            return self.subproject.project.make_subproject_select_options(user_id)
        elif self.project:
            return self.project.make_subproject_select_options(user_id)
        elif self.debit_card:
            return self.debit_card.project.make_subproject_select_options(user_id)
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
    def error_info(self):
        return "Betaling"


def get_total_route_amount(payments: List[Payment], routes: Tuple[str, ...]):
    return sum([x.transaction_amount for x in payments if x.route in routes])


def financial_summary(payments: List[Payment]):
    payments = sorted(payments, key=lambda x: x.booking_date)
    return {
        "awarded": format_currency_with_cents(
            get_total_route_amount(payments, ("inkomsten",))
        ),
        "insourcing": format_currency_with_cents(
            get_total_route_amount(payments, ("inbesteding",))
        ),
        "expenses": format_currency_with_cents(
            get_total_route_amount(payments, ("uitgaven", "inbesteding"))
        ),
        "first_payment_date": payments[0].booking_date.strftime("%d-%m-%Y")
        if len(payments) != 0
        else "geen",
        "last_payment_date": payments[-1].booking_date.strftime("%d-%m-%Y")
        if len(payments) != 0
        else "geen",
    }


class Funder(db.Model, DefaultCRUD, DefaultErrorMessages):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"))
    name = db.Column(db.String(120), index=True)
    url = db.Column(db.String(2000))
    subsidy = db.Column(db.String(120))
    subsidy_number = db.Column(db.String(120))
    budget = db.Column(db.Integer)
    justified = db.Column(db.Boolean, default=False)
    images = db.relationship("File", secondary=funder_image, lazy="dynamic")
    subprojects = db.relationship(
        "Subproject",
        secondary=subproject_funder,
        lazy="dynamic",
        back_populates="funders",
    )

    @property
    def formatted_budget(self):
        return "%s%s" % (
            "€ ",
            locale.format("%d", self.budget, grouping=True, monetary=True),
        )

    @classmethod
    def attach(cls, funders, subproject_id, **kwargs):
        subproject = Subproject.query.get(subproject_id)
        subproject.funders.extend(funders)
        db.session.add(subproject)
        db.session.commit()
        return subproject

    def detach(self, id, subproject_id, **kwargs):
        subproject = Subproject.query.get(subproject_id)
        subproject.funders.remove(Funder.query.get(id))
        db.session.add(subproject)
        db.session.commit()
        pass

    @property
    def error_info(self):
        return f"Sponsor '{self.name}'"

    @property
    def has_at_least_one_subproject(self):
        return len(self.subprojects.all()) > 0

    @property
    def can_be_justified(self):
        subprojects = self.subprojects.all()
        unfinished_subproject = any([not x.finished for x in subprojects])
        return (
            self.has_at_least_one_subproject
            and not unfinished_subproject
            and not self.justified
        )

    @property
    def formatted_name(self):
        return f"{self.name}, {self.subsidy} - {self.subsidy_number}"


class UserStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(240), index=True)
    title = db.Column(db.String(200))
    text = db.Column(db.String(200))
    hidden = db.Column(db.Boolean, default=False)
    images = db.relationship("File", secondary=user_story_image, lazy="dynamic")


def save_attachment(f, mediatype, db_object, folder):
    filename = secure_filename(f.filename)
    filename = "%s_%s" % (datetime.now(app.config["TZ"]).isoformat()[:19], filename)
    filepath = os.path.join(
        os.path.abspath(
            os.path.join(
                app.instance_path, "../%s/%s" % (app.config["UPLOAD_FOLDER"], folder)
            )
        ),
        filename,
    )
    f.save(filepath)

    if f.mimetype in ["image/jpeg", "image/jpg", "image/png"]:
        try:
            # TODO: Refactor.
            im = Image.open(f)
            im.thumbnail((320, 320), Image.ANTIALIAS)
            thumbnail_filename = os.path.splitext(filepath)[0] + "_thumb.jpeg"
            im.save(thumbnail_filename, "JPEG")
        except Exception as e:
            app.logger.error(repr(e))

    new_file = File(filename=filename, mimetype=f.headers[1][1], mediatype=mediatype)
    db.session.add(new_file)
    db.session.commit()

    # Link attachment to payment in the database
    # If the db object is a User, then save as FK and store the id
    if isinstance(db_object, (User, Project, Subproject)):
        db_object.image = new_file.id
        db.session.commit()
    # Elif this is a Payment, then save as many-to-many and we need to append
    elif isinstance(db_object, Payment):
        db_object.attachments.append(new_file)
        db.session.commit()

    return new_file


class File(db.Model, DefaultCRUD, DefaultErrorMessages):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), index=True)
    mimetype = db.Column(db.String(255))
    mediatype = db.Column(db.String(32))

    @classmethod
    def add_attachment(self, data_file, mediatype, payment_id):
        payment = Payment.query.get(payment_id)
        attachment = save_attachment(
            data_file, mediatype, payment, "transaction-attachment"
        )
        return attachment

    @property
    def error_info(self):
        return "Bestand"


class Category(db.Model, DefaultCRUD, DefaultErrorMessages):
    id = db.Column(db.Integer, primary_key=True)
    subproject_id = db.Column(
        db.Integer, db.ForeignKey("subproject.id", ondelete="CASCADE")
    )
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"))
    name = db.Column(db.String(120), index=True)
    payments = db.relationship("Payment", backref="category", lazy="dynamic")

    # Category names must be unique within a (sub)project
    __table_args__ = (db.UniqueConstraint("subproject_id", "name"),)

    def update(self, data):
        try:
            super(Category, self).update(data)
        except IntegrityError as e:
            app.logger.info(repr(e))
            raise ex.DuplicateCategoryName(data["name"])

    @classmethod
    def create(cls, data):
        try:
            return super(Category, cls).create(data)
        except IntegrityError as e:
            app.logger.info(repr(e))
            raise ex.DuplicateCategoryName(data["name"])

    @property
    def error_info(self):
        return f"Categorie '{self.name}'"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
