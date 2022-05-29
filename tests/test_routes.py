from app.models import Project, User, DebitCard


def test_add_project(db, client):
    response = client.post(
        "/",
        data={
            "name": "Test Project",
            "description": "A test.",
            "purpose": "To test.",
            "target_audience": "Developers.",
            "contains_subprojects": True,
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
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert Project.query.one()
    assert User.query.one()
    assert len(DebitCard.query.all()) == 3
