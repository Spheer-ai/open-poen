from app.forms import validate_budget
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, TextAreaField
from wtforms.validators import URL, DataRequired, Length, Optional, ValidationError
from wtforms.widgets import HiddenInput

LEGAL_ENTITIES = [
    (x, x)
    for x in [
        "Stichting",
        "Vereniging",
        "Eenmanszaak",
        "Vennootschap onder Firma",
        "Maatschap",
        "Besloten Vennootschap",
        "Coöperatie",
        "Geen (Natuurlijk Persoon)",
    ]
]


def validate_kvk(form, field):
    legal_entity = form._fields.get("legal_entity").data
    if legal_entity != "Geen (Natuurlijk Persoon)" and field.data == "":
        raise ValidationError(
            (
                "Een KvK-nummer is verplicht in het geval van de "
                f"rechtsvorm '{legal_entity}'."
            )
        )
    if legal_entity == "Geen (Natuurlijk Persoon)" and field.data != "":
        raise ValidationError(
            (
                "Een KvK-nummer mag niet worden opgegeven in het geval van een "
                "natuurlijk persoon."
            )
        )


class FunderForm(FlaskForm):
    class Meta:
        csrf = False

    id = IntegerField(widget=HiddenInput(), validators=[Optional()])
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    url = StringField("URL", validators=[DataRequired(), URL(), Length(max=2000)])
    subsidy = StringField(
        "(Subsidie-)regeling", validators=[DataRequired(), Length(max=120)]
    )
    subsidy_number = StringField(
        "Beschikkingsnummer / referentie", validators=[DataRequired(), Length(max=120)]
    )
    budget = IntegerField(
        "Budget van deze sponsor", validators=[DataRequired(), validate_budget]
    )


class SubprojectBaseForm(FlaskForm):
    id = IntegerField(widget=HiddenInput(), validators=[Optional()])
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Beschrijving", validators=[DataRequired()])
    purpose = TextAreaField("Doel", validators=[DataRequired()])
    target_audience = TextAreaField("Doelgroep", validators=[DataRequired()])
    budget = IntegerField(
        "Budget voor deze activiteit", validators=[Optional(), validate_budget]
    )
