from xmlrpc.client import Boolean
from wtforms.fields.core import FieldList, FormField
from app import app
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    URL,
    ValidationError,
)
from wtforms.widgets import HiddenInput, ListWidget, CheckboxInput
from wtforms import (
    StringField,
    IntegerField,
    BooleanField,
    PasswordField,
    SubmitField,
    SelectField,
    TextAreaField,
    DecimalField,
    DateField,
    RadioField,
    Form,
)
from wtforms.fields.html5 import EmailField
from app.models import DebitCard, Payment, Funder
from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField

allowed_extensions = [
    "jpg",
    "jpeg",
    "png",
    "txt",
    "pdf",
    "ods",
    "xls",
    "xlsx",
    "odt",
    "doc",
    "docx",
]


def trim_whitespace(x):
    """This if else is necessary because this filter is evaluated for some reason even when the form is
    not submitted. Probably a result of using wtforms in a way it was not intended for by an earlier
    developer."""
    if type(x) == str and len(x) > 0:
        return x.strip()
    else:
        return None


def validate_card_number(form, field):
    if not field.data.startswith("6731924"):
        raise ValidationError(
            (
                f"Betaalpas {field.data} begint niet met 6731924. Alle betaalpassen beginnen "
                "met deze cijferreeks."
            )
        )
    if not len(field.data) == 19:
        raise ValidationError(
            (
                f"Betaalpas {field.data} bestaat niet precies uit 19, maar uit {len(field.data)}"
                " cijfers. Alle betaalpassen bestaan precies uit 19 cijfers."
            )
        )


def validate_card_number_to_project(form, field):
    """A debit card can only be added to a project if it does not already exist, or if it exists, but is not
    already coupled to a project."""
    present_debit_card = DebitCard.query.filter_by(card_number=field.data).first()
    if present_debit_card is None:
        return
    if present_debit_card.project_id is None:
        return
    else:
        raise ValidationError(
            f"De betaalpas {field.data} is al gekoppeld aan een project."
        )


def validate_iban(form, field):
    if (
        field.data.startswith("NL")
        and field.data[4:7] == "BNG"
        and all([(x.isdigit()) for x in field.data[8:]])
    ):
        return
    else:
        raise ValidationError(f"{field.data} is niet een BNG-rekening.")


def validate_topup_amount(form, field):
    if field.data is None:
        return
    if field.data <= 0:
        raise ValidationError(
            f"{field.data} is niet een positief bedrag. Topups moeten meer dan 0 € zijn."
        )


def validate_budget(form, field):
    if field.data is not None and field.data < 0:
        raise ValidationError(
            f"{field.data} is een negatief bedrag. Een budget moet altijd positief of leeg zijn."
        )


def positive_integer(form, field):
    if field.data is None:
        return
    if field.data < 0:
        raise ValidationError(f"{field.data} is niet een positief getal.")


class BNGLinkForm(FlaskForm):
    iban = StringField("IBAN", validators=[DataRequired(), validate_iban])
    valid_until = DateField(
        "Geldig tot", format="%d-%m-%Y", validators=[DataRequired()]
    )
    submit = SubmitField("Aanmaken", render_kw={"class": "btn btn-info"})
    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})


class ResetPasswordRequestForm(FlaskForm):
    email = StringField(
        "E-mailadres", validators=[DataRequired(), Email(), Length(max=120)]
    )
    submit = SubmitField("Bevestig", render_kw={"class": "btn btn-info"})


class ResetPasswordForm(FlaskForm):
    # Use 'Wachtwoord' instead of 'password' as the variable
    # is used in a user-facing error message when the passwords
    # don't match and we want it to show a Dutch word instead of
    # English
    Wachtwoord = PasswordField(
        "Wachtwoord",
        validators=[DataRequired(), Length(min=12)],
        render_kw={"autocomplete": "new-password"},
    )
    Wachtwoord2 = PasswordField(
        "Herhaal wachtwoord",
        validators=[DataRequired(), EqualTo("Wachtwoord")],
        render_kw={"autocomplete": "new-password"},
    )
    submit = SubmitField("Bevestig", render_kw={"class": "btn btn-info"})


class LoginForm(FlaskForm):
    email = EmailField(
        "E-mailadres", validators=[DataRequired(), Email(), Length(max=120)]
    )
    Wachtwoord = PasswordField(
        "Wachtwoord",
        validators=[DataRequired(), Length(min=12)],
        render_kw={"autocomplete": "current-password"},
    )
    submit = SubmitField("Inloggen", render_kw={"class": "btn btn-info"})


class NewProjectFunderForm(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    url = StringField("URL", validators=[DataRequired(), URL(), Length(max=2000)])


class EditDebitCardForm(FlaskForm):
    remove_from_project = BooleanField("Ontkoppel betaalpas van dit initiatief")
    id = IntegerField(widget=HiddenInput(), validators=[Optional()])
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class DebitCardForm(FlaskForm):
    card_number = StringField(
        "Pasnummer",
        validators=[
            DataRequired(),
            validate_card_number_to_project,
            validate_card_number,
        ],
        filters=[trim_whitespace],
    )
    project_id = IntegerField(widget=HiddenInput(), validators=[Optional()])
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class SubprojectForm(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Beschrijving", validators=[DataRequired()])
    purpose = TextAreaField("Doel", validators=[DataRequired()])
    target_audience = TextAreaField("Doelgroep", validators=[DataRequired()])
    hidden = BooleanField("Activiteit verbergen")
    budget = IntegerField(
        "Budget voor deze activiteit", validators=[Optional(), validate_budget]
    )
    project_id = IntegerField(widget=HiddenInput())
    id = IntegerField(widget=HiddenInput())
    funder = QuerySelectMultipleField(
        "Funder",
        option_widget=CheckboxInput(),
        get_label="name",
    )
    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})
    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})


# Allow both dot '.' and comma ',' as decimal separator
class FlexibleDecimalField(DecimalField):
    def process_formdata(self, valuelist):
        if valuelist:
            valuelist[0] = valuelist[0].replace(",", ".")
        return super(FlexibleDecimalField, self).process_formdata(valuelist)


# Add a new payment manually
class NewTopupForm(FlaskForm):
    transaction_amount = FlexibleDecimalField(
        "Bedrag (moet positief zijn voor topups.)", validators=[validate_topup_amount]
    )
    booking_date = DateField("Datum (notatie: dd-mm-jjjj)", format="%d-%m-%Y")
    card_number = StringField(
        "Pasnummer",
        validators=[DataRequired(), validate_card_number],
        filters=[trim_whitespace],
    )
    short_user_description = StringField(
        "Korte beschrijving", validators=[Length(max=50)]
    )
    long_user_description = TextAreaField(
        "Lange beschrijving", validators=[Length(max=2000)]
    )
    hidden = BooleanField("Transactie verbergen")
    data_file = FileField(
        "Bestand",
        validators=[
            FileAllowed(
                allowed_extensions,
                (
                    "bestandstype niet toegstaan. Enkel de volgende "
                    "bestandstypen worden geaccepteerd: %s"
                    % ", ".join(allowed_extensions)
                ),
            ),
            Optional(),
        ],
    )
    mediatype = RadioField(
        "Media type",
        choices=[("media", "media"), ("bon", "bon")],
        default="bon",
        validators=[Optional()],
    )
    project_id = IntegerField(widget=HiddenInput())
    subproject_id = IntegerField(widget=HiddenInput())
    type = StringField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class NewPaymentForm(FlaskForm):
    transaction_amount = FlexibleDecimalField(
        "Bedrag (begin met een - als het een uitgave is)"
    )
    booking_date = DateField("Datum (notatie: dd-mm-jjjj)", format="%d-%m-%Y")
    debtor_name = StringField("Verstuurder naam", validators=[Length(max=120)])
    debtor_account = StringField("Verstuurder IBAN", validators=[Length(max=120)])
    creditor_name = StringField("Ontvanger naam", validators=[Length(max=120)])
    creditor_account = StringField("Ontvanger IBAN", validators=[Length(max=120)])
    short_user_description = StringField(
        "Korte beschrijving", validators=[Length(max=50)]
    )
    long_user_description = TextAreaField(
        "Lange beschrijving", validators=[Length(max=2000)]
    )
    hidden = BooleanField("Transactie verbergen")
    data_file = FileField(
        "Bestand",
        validators=[
            FileAllowed(
                allowed_extensions,
                (
                    "bestandstype niet toegstaan. Enkel de volgende "
                    "bestandstypen worden geaccepteerd: %s"
                    % ", ".join(allowed_extensions)
                ),
            ),
            Optional(),
        ],
    )
    mediatype = RadioField(
        "Media type",
        choices=[("media", "media"), ("bon", "bon")],
        default="bon",
        validators=[Optional()],
    )
    project_id = IntegerField(widget=HiddenInput())
    subproject_id = IntegerField(widget=HiddenInput())
    type = StringField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class NewTopupForm(FlaskForm):
    transaction_amount = FlexibleDecimalField(
        "Bedrag (Topups moeten meer dan 0,00 euro bedragen.)",
        validators=[validate_topup_amount],
    )
    booking_date = DateField("Datum (notatie: dd-mm-jjjj)", format="%d-%m-%Y")
    card_number = SelectField("Betaalpas", choices=[])
    short_user_description = StringField(
        "Korte beschrijving", validators=[Length(max=50)]
    )
    long_user_description = TextAreaField(
        "Lange beschrijving", validators=[Length(max=2000)]
    )
    hidden = BooleanField("Transactie verbergen")
    data_file = FileField(
        "Bestand",
        validators=[
            FileAllowed(
                allowed_extensions,
                (
                    "bestandstype niet toegstaan. Enkel de volgende "
                    "bestandstypen worden geaccepteerd: %s"
                    % ", ".join(allowed_extensions)
                ),
            ),
            Optional(),
        ],
    )
    mediatype = RadioField(
        "Media type",
        choices=[("media", "media"), ("bon", "bon")],
        default="bon",
        validators=[Optional()],
    )
    project_id = IntegerField(widget=HiddenInput())
    subproject_id = IntegerField(widget=HiddenInput())
    type = StringField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


# Edit a payment
class PaymentForm(FlaskForm):
    short_user_description = StringField(
        "Korte beschrijving", validators=[Length(max=50)]
    )
    long_user_description = TextAreaField(
        "Lange beschrijving", validators=[Length(max=2000)]
    )
    transaction_amount = FlexibleDecimalField(
        'Bedrag (begin met een "-" als het een uitgave is)'
    )
    booking_date = DateField("Datum (notatie: dd-mm-jjjj)", format="%d-%m-%Y")
    hidden = BooleanField("Transactie verbergen")
    category_id = SelectField("Categorie", validators=[Optional()], choices=[])
    route = SelectField(
        "Route",
        validators=[Optional()],
        choices=[
            ("inkomsten", "inkomsten"),
            ("uitgaven", "uitgaven"),
            ("inbesteding", "inbesteding"),
        ],
    )
    subproject_id = SelectField("Activiteit", validators=[Optional()], choices=[])
    id = IntegerField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})

    # Only manually added payments are allowed to be removed
    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})


class TransactionAttachmentForm(FlaskForm):
    data_file = FileField(
        "Bestand",
        validators=[
            FileRequired(),
            FileAllowed(
                allowed_extensions,
                (
                    "bestandstype niet toegstaan. Enkel de volgende "
                    "bestandstypen worden geaccepteerd: %s"
                    % ", ".join(allowed_extensions)
                ),
            ),
        ],
    )
    mediatype = RadioField(
        "Media type",
        choices=[("media", "media"), ("bon", "bon")],
        default="bon",
        validators=[DataRequired()],
    )
    payment_id = IntegerField(widget=HiddenInput())
    submit = SubmitField("Uploaden", render_kw={"class": "btn btn-info"})


class EditAttachmentForm(FlaskForm):
    id = IntegerField(widget=HiddenInput())
    mediatype = RadioField(
        "Media type",
        choices=[("media", "media"), ("bon", "bon")],
        validators=[DataRequired()],
    )

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})

    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})


class AddUserForm(FlaskForm):
    email = StringField(
        "E-mailadres", validators=[DataRequired(), Email(), Length(max=120)]
    )
    admin = BooleanField(widget=HiddenInput())
    financial = BooleanField(widget=HiddenInput())
    project_id = IntegerField(widget=HiddenInput())
    subproject_id = IntegerField(widget=HiddenInput())

    submit = SubmitField("Uitnodigen", render_kw={"class": "btn btn-info"})


class EditAdminForm(FlaskForm):
    admin = BooleanField("Admin")
    financial = BooleanField("Financial")
    active = BooleanField("Gebruikersaccount is actief")
    id = IntegerField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class EditProjectOwnerForm(FlaskForm):
    hidden = BooleanField("Initiatiefnemer verbergen in initiatiefnemersoverzicht")
    remove_from_project = BooleanField("Verwijder initiatiefnemer van dit initiatief")
    active = BooleanField("Initiatiefnemer account is actief")
    id = IntegerField(widget=HiddenInput())
    project_id = IntegerField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class EditUserForm(FlaskForm):
    hidden = BooleanField("Activiteitnemer verbergen in activiteitnemersoverzicht")
    remove_from_subproject = BooleanField("Verwijder activiteitnemer van dit project")
    active = BooleanField("Activiteitnemer account is actief")
    id = IntegerField(widget=HiddenInput())
    subproject_id = IntegerField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class EditProfileForm(FlaskForm):
    first_name = StringField("Voornaam", validators=[DataRequired(), Length(max=120)])
    last_name = StringField("Achternaam", validators=[DataRequired(), Length(max=120)])
    biography = TextAreaField(
        "Beschrijving", validators=[DataRequired(), Length(max=1000)]
    )

    allowed_extensions = ["jpg", "jpeg", "png"]
    data_file = FileField(
        "Profielfoto (als u al een profielfoto heeft en een nieuwe toevoegt dan wordt de oude verwijderd)",
        validators=[
            FileAllowed(
                allowed_extensions,
                (
                    "bestandstype niet toegstaan. Enkel de volgende "
                    "bestandstypen worden geaccepteerd: %s"
                    % ", ".join(allowed_extensions)
                ),
            )
        ],
    )

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})


class CategoryForm(FlaskForm):
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    id = IntegerField(widget=HiddenInput())
    project_id = IntegerField(widget=HiddenInput())
    subproject_id = IntegerField(widget=HiddenInput())

    submit = SubmitField("Opslaan", render_kw={"class": "btn btn-info"})

    remove = SubmitField("Verwijderen", render_kw={"class": "btn btn-danger"})
