from app import app, db, cli
from app.models import (
    User,
    Project,
    Subproject,
    DebitCard,
    Funder,
    Payment,
    UserStory,
    File,
    Category,
)


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "User": User,
        "Project": Project,
        "Subproject": Subproject,
        "DebitCard": DebitCard,
        "Funder": Funder,
        "Payment": Payment,
        "UserStory": UserStory,
        "File": File,
        "Category": Category,
    }
