from app.models import Project, User, DebitCard


create_project_post = {
    "name": "Test Project",
    "description": "A test.",
    "purpose": "To test.",
    "target_audience": "Developers.",
    "owner": "Mark de Wijk",
    "owner_email": "markdewijk@spheer.ai",
    "legal_entity": "Stichting",
    "address_applicant": "Hereweg 14, Groningen",
    "registration_kvk": "1111111111",
    "project_location": "Groningen",
    "budget": 10000,
    "project_owners-0-email": "markdewijk@spheer.ai",
    "card_numbers-0-card_number": "6731924673192111111",
    "card_numbers-1-card_number": "6731924673192111112",
    "card_numbers-2-card_number": "6731924673192111113",
}
# Adding the form's prefix.
form_prefix = "create_project_form-"
create_project_post = {form_prefix + k: v for k, v in create_project_post.items()}


def test_add_project(client):
    response = client.post(
        "/",
        data=create_project_post,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert Project.query.one()
    assert User.query.one()
    assert len(DebitCard.query.all()) == 3


def test_duplicate_project_owners(client):
    response = client.post(
        "/",
        data={
            **create_project_post,
            form_prefix + "project_owners-1-email": "markdewijk@spheer.ai",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    users = User.query.all()
    assert len(users) == 1
    assert users[0].email == "markdewijk@spheer.ai"
