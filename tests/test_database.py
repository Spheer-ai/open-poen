#!/usr/bin/env python

import unittest

from app import app, db, util
from app.models import User, Project, Payment, Subproject, DebitCard
from decimal import *
import pandas as pd


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
        payments = pd.read_csv("tests/payments_1.csv")
        payments = payments[["route", "amount_value", "short_user_description", "long_user_description"]].to_dict(orient="records")
        payments = [Payment(**x) for x in payments]
        project.payments.extend(payments)
        db.session.add(project)
        db.session.commit()

        project_amounts = util.calculate_project_amounts(project.id)

        self.assertTrue(project_amounts["awarded"] == 10000)
        self.assertTrue(project_amounts["spent"] == 5145.6)
        self.assertTrue(project_amounts["left_str"] == "€ 4.854")

    def test_business_rules_scenario_2(self):
        self.assertTrue(True)

    def test_business_rules_scenario_3(self):
        self.assertTrue(True)

    def test_business_rules_scenario_4(self):
        self.assertTrue(True)

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
