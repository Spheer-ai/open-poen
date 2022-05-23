from re import S
from app.better_utils import format_flash


class BaseException(Exception):
    @property
    def flash(self):
        return format_flash(str(self), color="red")


class CoupledDebitCardHasPayments(BaseException):
    def __init__(self, card_number: str):
        self.card_number = card_number

    def __str__(self):
        return (
            f"Betaalpas '{self.card_number}' kan niet worden ontkoppeld, "
            "omdat er al betalingen mee zijn gedaan."
        )


class DoubleSubprojectName(BaseException):
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return (
            f"Het is niet mogelijk '{self.name}' als naam te gebruiken voor "
            "deze activiteit, omdat het bijbehorende initiatief al een "
            "activiteit heeft met deze naam."
        )


class UserIsAlreadyPresentInProject(BaseException):
    def __init__(self, email: str):
        self.email = email

    def __str__(self):
        return (
            f"Gebruiker '{self.email}' is niet toegevoegd, omdat deze al "
            "initiatiefnemer was van dit initiatief."
        )


class UserIsAlreadyPresentInSubproject(BaseException):
    def __init__(self, email: str):
        self.email = email

    def __str__(self):
        return (
            f"Gebruiker '{self.email}' is niet toegevoegd, omdat deze al "
            "activiteitnemer was van deze activiteit."
        )


class DuplicateCategoryName(BaseException):
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return (
            f"Categorie '{self.name}' is niet goevoegd, omdat er al een "
            "categorie bestaat met deze naam."
        )


class DuplicateProjectName(BaseException):
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return (
            f"Project '{self.name}' is niet goevoegd, omdat er al een "
            "project bestaat met deze naam."
        )


known_exceptions = (
    CoupledDebitCardHasPayments,
    DoubleSubprojectName,
    UserIsAlreadyPresentInProject,
    UserIsAlreadyPresentInSubproject,
    DuplicateCategoryName,
    DuplicateProjectName,
)
