import unittest
from app import create_app, db
from app.models import User
from config import TestingConfig


class UserModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_setter(self):
        u = User()
        u.set_password('cat')
        self.assertTrue(u.password_hash is not None)

    def test_password_verification(self):
        u = User()
        u.set_password('cat')
        self.assertTrue(u.check_password('cat'))
        self.assertFalse(u.check_password('dog'))

    def test_password_salts_are_random(self):
        u1 = User()
        u1.set_password('cat')
        u2 = User()
        u2.set_password('cat')
        self.assertNotEqual(u1.password_hash, u2.password_hash)
