import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def staff_client(db):
    User = get_user_model()
    user = User.objects.create_user('nihar', 'n@example.com', 'pw', is_staff=True)
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def anon_client():
    return Client()
