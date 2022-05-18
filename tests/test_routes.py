from app.models import Project


def test_add_project(db, client):
    response = client.post(
        "/",
        data={
            "name": "Buurtborrel Oranjebuurt",
            "description": "Buurtborrel / -BBQ voor de Oranjebuurt in Groningen.",
            "purpose": "Creëren van saamhorigheid/gemeenschapsgevoel in de Oranjebuurt",
            "target_audience": "40+ en jonger dan 18.",
            "contains_subprojects": True,
            "owner": "Jaap Koen Bijma",
            "owner_email": "jaapkoenbijma@amsterdam.nl",
            "legal_entity": "Stichting",
            "address_applicant": "De Dam 14, 9889 ST",
            "registration_kvk": "1334998890",
            "project_location": "Amsterdam",
            "budget": 300,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    projects = Project.query.all()
    assert len(projects) == 1
    assert projects[0].name == "Buurtborrel Oranjebuurt"
