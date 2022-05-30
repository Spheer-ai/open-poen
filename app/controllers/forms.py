from app.forms import validate_budget
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, TextAreaField
from wtforms.validators import URL, DataRequired, Length, Optional
from wtforms.widgets import HiddenInput


class FunderForm(FlaskForm):
    class Meta:
        csrf = False

    id = IntegerField(widget=HiddenInput(), validators=[Optional()])
    name = StringField("Naam", validators=[DataRequired(), Length(max=120)])
    url = StringField("URL", validators=[DataRequired(), URL(), Length(max=2000)])
    subsidy = StringField(
        "Subsidieregeling", validators=[DataRequired(), Length(max=120)]
    )
    subsidy_number = StringField(
        "Beschikkingsnummer", validators=[DataRequired(), Length(max=120)]
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
