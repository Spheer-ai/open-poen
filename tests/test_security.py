from app.models import User


def test_password_hashing():
    u = User(first_name="testuser")
    u.set_password("testpassword")
    assert not u.check_password("notthetestpassword")
    assert u.check_password("testpassword")
