import pytest
from presentations.models import Session, Participant, Response, Comment

pytestmark = pytest.mark.django_db


def test_session_defaults_and_bump():
    s = Session.objects.create(deck_slug='ex')
    assert len(s.join_code) == 6 and s.join_code.isupper()
    assert s.version == 0 and s.is_locked is False and s.ended_at is None
    s.bump()
    assert Session.objects.get(pk=s.pk).version == 1


def test_set_slide_and_interaction_state():
    s = Session.objects.create(deck_slug='ex')
    s.set_slide('orbits')
    s.set_interaction_state('q1', 'open')
    s.refresh_from_db()
    assert s.current_slide_id == 'orbits'
    assert s.interaction_states == {'q1': 'open'}
    assert s.version == 2


def test_invalid_interaction_state_rejected():
    s = Session.objects.create(deck_slug='ex')
    with pytest.raises(ValueError):
        s.set_interaction_state('q1', 'bogus')


def test_lock_reveals_touched_only():
    s = Session.objects.create(deck_slug='ex')
    s.set_interaction_state('a', 'open')
    s.set_interaction_state('b', 'closed')
    s.lock()
    s.refresh_from_db()
    assert s.is_locked and s.ended_at is not None
    assert s.interaction_states == {'a': 'revealed', 'b': 'revealed'}
    s.unlock()
    s.refresh_from_db()
    assert not s.is_locked and s.ended_at is None


def test_open_for_and_archived_for():
    old = Session.objects.create(deck_slug='ex')
    old.lock()
    live = Session.objects.create(deck_slug='ex')
    assert Session.open_for('ex') == live
    assert Session.archived_for('ex') == old
    assert Session.open_for('nope') is None


def test_response_unique_per_participant_interaction():
    s = Session.objects.create(deck_slug='ex')
    p = Participant.objects.create(session=s, expertise_tag='theory')
    assert len(p.token) == 32
    Response.objects.create(participant=p, session=s, interaction_id='q1', payload={'choice': 'A'})
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        Response.objects.create(participant=p, session=s, interaction_id='q1', payload={'choice': 'B'})


def test_comment_visible_manager():
    Comment.objects.create(deck_slug='ex', slide_id='s', body='hi')
    Comment.objects.create(deck_slug='ex', slide_id='s', body='spam', is_hidden=True)
    assert Comment.visible.filter(deck_slug='ex').count() == 1
