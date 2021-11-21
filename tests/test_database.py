#!/usr/bin/env python

import unittest

from app import app, db, util
from app.models import User, Project, Payment, Subproject, DebitCard
from decimal import *
import pandas as pd


def payment(r, av, sad):
    return {"route": r, "amount_value": av, "short_user_description": sad}


class TestDatabase(unittest.TestCase):
    def setUp(self):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_password_hashing(self):
        u = User(first_name='testuser')
        u.set_password('testpassword')
        self.assertFalse(u.check_password('notthetestpassword'))
        self.assertTrue(u.check_password('testpassword'))

    def test_business_rules_scenario_1(self):
        project = Project(name="Scenario 1", budget=10000, contains_subprojects=False)
        
        payments = [
            payment("subsidie", 10000, "subsidie"),
            payment("aanbesteding", -5000, "workshop"),
            payment("aanbesteding", -22.50, "metro"),
            payment("aanbesteding", -133.10, "tekenmateriaal"),
            payment("aanbesteding", 10, "correctie metro")
        ]
        payments = [Payment(**x) for x in payments]
        project.payments.extend(payments)
        db.session.add(project)
        db.session.commit()

        project_amounts = util.calculate_project_amounts(project.id)

        self.assertTrue(project_amounts["awarded"] == 10000)
        self.assertTrue(project_amounts["spent"] == 5145.6)
        self.assertTrue(project_amounts["left_str"] == "€ 4.854")

    def test_business_rules_scenario_2(self):
        project = Project(name="Scenario 2", budget=21000, contains_subprojects=True)
        subproject_1, subproject_2 = [Subproject(**x) for x in [
            {"name": "Subproject 1", "budget": 10000},
            {"name": "Subproject 2", "budget": 11000}
        ]]
        payments_1 = [Payment(**x) for x in [
            payment("aanbesteding", -5000, "workshop"),
            payment("aanbesteding", -22.50, "metro"),
            payment("aanbesteding", 10, "correctie metro")
        ]]
        payments_2 = [Payment(**x) for x in [
            payment("subsidie", 5500, "ontvangen subsidie"),
            payment("aanbesteding", -133.10, "tekenmateriaal")
        ]]
        subproject_1.payments = payments_1
        subproject_2.payments = payments_2
        project.subprojects = [subproject_1, subproject_2]
        db.session.add(project)
        db.session.commit()

        project_amounts = util.calculate_project_amounts(project.id)
        subproject_1_amounts = util.calculate_subproject_amounts(subproject_1.id)
        subproject_2_amounts = util.calculate_subproject_amounts(subproject_2.id)

        self.assertTrue(project_amounts["awarded"] == 5500)
        self.assertTrue(project_amounts["spent"] == 5145.6)
        self.assertTrue(project_amounts["left_str"] == "€ 15.854")

        self.assertTrue(subproject_1_amounts["awarded"] == 0)
        self.assertTrue(subproject_1_amounts["spent"] == 5012.5)
        self.assertTrue(subproject_1_amounts["left_str"] == "€ 4.988")

        self.assertTrue(subproject_2_amounts["awarded"] == 5500)
        self.assertTrue(subproject_2_amounts["spent"] == 133.1)
        self.assertTrue(subproject_2_amounts["left_str"] == "€ 10.867")

    def test_business_rules_scenario_3(self):
        project = Project(name="Scenario 3", budget=50000, contains_subprojects=False)
        
        payments = [
            payment("subsidie", 25000, "ontvangen subsidie"),
            payment("subsidie", 10000, "ontvangen subsidie deel 2"),
            payment("aanbesteding", -5000, "workshop"),
            payment("aanbesteding", -133.10, "tekenmateriaal"),
            payment("aanbesteding", -22.50, "metro"),
            payment("aanbesteding", 10, "correctie metro")
        ]
        payments = [Payment(**x) for x in payments]
        project.payments.extend(payments)
        db.session.add(project)
        db.session.commit()

        project_amounts = util.calculate_project_amounts(project.id)

        self.assertTrue(project_amounts["awarded"] == 35000)
        self.assertTrue(project_amounts["spent"] == 5145.6)
        self.assertTrue(project_amounts["left_str"] == "€ 44.854")

    def test_business_rules_scenario_4(self):
        project = Project(name="Scenario 4", budget=21000, contains_subprojects=True)
        subproject_1, subproject_2 = [Subproject(**x) for x in [
            {"name": "Subproject 1", "budget": 10000},
            {"name": "Subproject 2", "budget": 11000}
        ]]
        payments_1 = [Payment(**x) for x in [
            payment("aanbesteding", -5000, "workshop"),
            payment("aanbesteding", -22.50, "metro"),
            payment("aanbesteding", 10, "correctie metro"),
            payment("subsidie", 6000, "ontvangen subsidie termijn 1")
        ]]
        payments_2 = [Payment(**x) for x in [
            payment("subsidie", 5000, "ontvangen subsidie termijn 1"),
            payment("aanbesteding", -133.10, "tekenmateriaal")
        ]]
        subproject_1.payments = payments_1
        subproject_2.payments = payments_2
        project.subprojects = [subproject_1, subproject_2]
        db.session.add(project)
        db.session.commit()

        project_amounts = util.calculate_project_amounts(project.id)
        subproject_1_amounts = util.calculate_subproject_amounts(subproject_1.id)
        subproject_2_amounts = util.calculate_subproject_amounts(subproject_2.id)

        self.assertTrue(project_amounts["awarded"] == 11000)
        self.assertTrue(project_amounts["spent"] == 5145.6)
        self.assertTrue(project_amounts["left_str"] == "€ 15.854")

        self.assertTrue(subproject_1_amounts["awarded"] == 6000)
        self.assertTrue(subproject_1_amounts["spent"] == 5012.5)
        self.assertTrue(subproject_1_amounts["left_str"] == "€ 4.988")

        self.assertTrue(subproject_2_amounts["awarded"] == 5000)
        self.assertTrue(subproject_2_amounts["spent"] == 133.1)
        self.assertTrue(subproject_2_amounts["left_str"] == "€ 10.867")

    def test_user_project_subproject(self):
        # Add data
        db.session.add(Project(name='testproject'))
        db.session.add(
            Subproject(name='testsubproject1', iban="NL00BUNQ0123456789")
        )
        db.session.add(
            Subproject(name='testsubproject2', iban="NL00BUNQ0123456780")
        )
        db.session.add(
            User(first_name='testuser1', email='testuser1@example.com')
        )
        db.session.add(
            User(first_name='testuser2', email='testuser2@example.com')
        )
        db.session.add(DebitCard(card_id=1))
        db.session.add(DebitCard(card_id=2))

        # Get data
        p = Project.query.get(1)
        s1 = Subproject.query.get(1)
        s2 = Subproject.query.get(2)
        u1 = User.query.get(1)
        u2 = User.query.get(2)
        d1 = DebitCard.query.get(1)
        d2 = DebitCard.query.get(2)

        # Add two users and two subprojects to a project
        p.users.append(u1)
        p.users.append(u2)
        s1.project_id = p.id
        s2.project_id = p.id
        self.assertEqual(p.users[0].first_name, 'testuser1')
        self.assertEqual(u1.projects[0].name, 'testproject')
        self.assertEqual(p.subprojects[0].name, 'testsubproject1')
        self.assertEqual(p.subprojects[1].name, 'testsubproject2')
        self.assertEqual(s1.project.name, 'testproject')

        # Add two debit cards to one user
        d1.user_id = u1.id
        d2.user_id = u1.id
        self.assertEqual(u1.debit_cards[0].card_id, 1)
        self.assertEqual(u1.debit_cards[1].card_id, 2)
        self.assertEqual(d1.user.first_name, 'testuser1')
        self.assertEqual(d2.user.first_name, 'testuser1')

        # Add two debit cards to one subproject
        d1.iban = s1.iban
        d2.iban = s1.iban
        self.assertEqual(s1.debit_cards[0].card_id, 1)
        self.assertEqual(s1.debit_cards[1].card_id, 2)
        self.assertEqual(d1.subproject.name, 'testsubproject1')
        self.assertEqual(d2.subproject.name, 'testsubproject1')
