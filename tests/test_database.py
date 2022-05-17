#!/usr/bin/env python

import pytest
from app import db, util, app
from app.models import User, Project, Payment, Subproject, DebitCard


@pytest.fixture()
def flask_app():
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.create_all()
    yield app
    db.session.remove()
    db.drop_all()


@pytest.fixture()
def client(app):
    return flask_app.test_client()


def payment(r, av, sad):
    return {"route": r, "transaction_amount": av, "short_user_description": sad}


def test_password_hashing():
    u = User(first_name="testuser")
    u.set_password("testpassword")
    assert not u.check_password("notthetestpassword")
    assert u.check_password("testpassword")


def test_business_rules_scenario_1(flask_app):
    project = Project(name="Scenario 1", budget=10000, contains_subprojects=False)

    payments = [
        payment("inkomsten", 10000, "subsidie"),
        payment("uitgaven", -5000, "workshop"),
        payment("uitgaven", -22.50, "metro"),
        payment("uitgaven", -133.10, "tekenmateriaal"),
        payment("uitgaven", 10, "correctie metro"),
    ]
    payments = [Payment(**x) for x in payments]
    project.payments.extend(payments)
    db.session.add(project)
    db.session.commit()

    project_amounts = util.calculate_amounts(
        Project, project.id, project.payments.all()
    )

    assert project_amounts["awarded"] == 10000
    assert project_amounts["spent"] == 5145.6
    assert project_amounts["left_str"] == "€ 4.854"


def test_business_rules_scenario_2(flask_app):
    project = Project(name="Scenario 2", budget=21000, contains_subprojects=True)
    subproject_1, subproject_2 = [
        Subproject(**x)
        for x in [
            {"name": "Subproject 1", "budget": 10000},
            {"name": "Subproject 2", "budget": 11000},
        ]
    ]
    payments_1 = [
        Payment(**x)
        for x in [
            payment("uitgaven", -5000, "workshop"),
            payment("uitgaven", -22.50, "metro"),
            payment("uitgaven", 10, "correctie metro"),
        ]
    ]
    payments_2 = [
        Payment(**x)
        for x in [
            payment("inkomsten", 5500, "ontvangen subsidie"),
            payment("uitgaven", -133.10, "tekenmateriaal"),
        ]
    ]
    # Note how payments have to be linked to both the project AND the subproject.
    subproject_1.payments = payments_1
    subproject_2.payments = payments_2
    project.subprojects = [subproject_1, subproject_2]
    project.payments = payments_1 + payments_2
    db.session.add(project)
    db.session.commit()

    project_amounts = util.calculate_amounts(
        Project, project.id, project.payments.all()
    )
    subproject_1_amounts = util.calculate_amounts(
        Subproject, subproject_1.id, subproject_1.payments.all()
    )
    subproject_2_amounts = util.calculate_amounts(
        Subproject, subproject_2.id, subproject_2.payments.all()
    )

    assert project_amounts["awarded"] == 5500
    assert project_amounts["spent"] == 5145.6
    assert project_amounts["left_str"] == "€ 15.854"

    assert subproject_1_amounts["awarded"] == 0
    assert subproject_1_amounts["spent"] == 5012.5
    assert subproject_1_amounts["left_str"] == "€ 4.988"

    assert subproject_2_amounts["awarded"] == 5500
    assert subproject_2_amounts["spent"] == 133.1
    assert subproject_2_amounts["left_str"] == "€ 10.867"


def test_business_rules_scenario_3(flask_app):
    project = Project(name="Scenario 3", budget=50000, contains_subprojects=False)

    payments = [
        payment("inkomsten", 25000, "ontvangen subsidie"),
        payment("inkomsten", 10000, "ontvangen subsidie deel 2"),
        payment("uitgaven", -5000, "workshop"),
        payment("uitgaven", -133.10, "tekenmateriaal"),
        payment("uitgaven", -22.50, "metro"),
        payment("uitgaven", 10, "correctie metro"),
    ]
    payments = [Payment(**x) for x in payments]
    project.payments.extend(payments)
    db.session.add(project)
    db.session.commit()

    project_amounts = util.calculate_amounts(
        Project, project.id, project.payments.all()
    )

    project_amounts["awarded"] == 35000
    project_amounts["spent"] == 5145.6
    project_amounts["left_str"] == "€ 44.854"


def test_business_rules_scenario_4(flask_app):
    project = Project(name="Scenario 4", budget=21000, contains_subprojects=True)
    subproject_1, subproject_2 = [
        Subproject(**x)
        for x in [
            {"name": "Subproject 1", "budget": 10000},
            {"name": "Subproject 2", "budget": 11000},
        ]
    ]
    payments_1 = [
        Payment(**x)
        for x in [
            payment("uitgaven", -5000, "workshop"),
            payment("uitgaven", -22.50, "metro"),
            payment("uitgaven", 10, "correctie metro"),
            payment("inkomsten", 6000, "ontvangen subsidie termijn 1"),
        ]
    ]
    payments_2 = [
        Payment(**x)
        for x in [
            payment("inkomsten", 5000, "ontvangen subsidie termijn 1"),
            payment("uitgaven", -133.10, "tekenmateriaal"),
        ]
    ]
    subproject_1.payments = payments_1
    subproject_2.payments = payments_2
    project.subprojects = [subproject_1, subproject_2]
    project.payments = payments_1 + payments_2
    db.session.add(project)
    db.session.commit()

    project_amounts = util.calculate_amounts(
        Project, project.id, project.payments.all()
    )
    subproject_1_amounts = util.calculate_amounts(
        Subproject, subproject_1.id, subproject_1.payments.all()
    )
    subproject_2_amounts = util.calculate_amounts(
        Subproject, subproject_2.id, subproject_2.payments.all()
    )

    assert project_amounts["awarded"] == 11000
    assert project_amounts["spent"] == 5145.6
    assert project_amounts["left_str"] == "€ 15.854"
    assert subproject_1_amounts["awarded"] == 6000
    assert subproject_1_amounts["spent"] == 5012.5
    assert subproject_1_amounts["left_str"] == "€ 4.988"
    assert subproject_2_amounts["awarded"] == 5000
    assert subproject_2_amounts["spent"] == 133.1
    assert subproject_2_amounts["left_str"] == "€ 10.867"
