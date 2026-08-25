"""The three deck surfaces must hand out a csrftoken cookie: core.js reads it for every POST."""
import json

import pytest
from django.test import Client

from presentations import registry
from presentations.models import Session

pytestmark = pytest.mark.django_db


@pytest.fixture
def example():
    registry.clear_cache()
    yield registry.get_deck('example')
    registry.clear_cache()


def _comment(client, slide, text, token=None):
    extra = {'HTTP_X_CSRFTOKEN': token} if token else {}
    return client.post('/presentations/example/comment/', data=json.dumps({'slide': slide, 'body': text}),
                       content_type='application/json', **extra)


def test_archive_sets_csrf_cookie_and_comment_posts_with_it(example):
    c = Client(enforce_csrf_checks=True)
    r = c.get('/presentations/example/')
    assert r.status_code == 200
    assert 'csrftoken' in c.cookies
    token = c.cookies['csrftoken'].value
    assert b'csrfmiddlewaretoken' in r.content          # the form carries {% csrf_token %} too
    assert _comment(c, example.slides[0].id, 'with token', token).status_code == 201


def test_comment_post_without_csrf_header_is_rejected(example):
    c = Client(enforce_csrf_checks=True)
    assert c.get('/presentations/example/').status_code == 200
    assert _comment(c, example.slides[0].id, 'no token').status_code == 403


def test_phone_join_page_sets_csrf_cookie_and_join_posts_with_it(example, staff_client):
    staff_client.get('/presentations/example/present/')
    code = Session.open_for('example').join_code
    c = Client(enforce_csrf_checks=True)
    r = c.get(f'/p/{code}/')
    assert r.status_code == 200
    assert 'csrftoken' in c.cookies
    token = c.cookies['csrftoken'].value
    r2 = c.post(f'/p/{code}/join/', {'expertise_tag': example.expertise[0], 'display_name': 'Ana'},
                HTTP_X_CSRFTOKEN=token)
    assert r2.status_code == 302


def test_present_page_sets_csrf_cookie(example, staff_client):
    r = staff_client.get('/presentations/example/present/')
    assert r.status_code == 200
    assert 'csrftoken' in staff_client.cookies
