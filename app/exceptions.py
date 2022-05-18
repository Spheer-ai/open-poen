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


known_exceptions = CoupledDebitCardHasPayments, DoubleSubprojectName
