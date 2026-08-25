import json
import pytest
from django.test import Client
from presentations import registry
from presentations.models import Session, Comment

pytestmark = pytest.mark.django_db


def test_full_session_flow(staff_client, settings):
    registry.clear_cache()
    # 1. presenter opens the deck → session exists, QR points at /p/<code>/
    page = staff_client.get('/presentations/example/present/').content.decode()
    s = Session.open_for('example'); code = s.join_code
    assert f'/p/{code}/' in page
    # 2. phones join with different tags (three 'theory' so that tag's slice clears
    # the n>=3 privacy floor from spec §8 "Expertise slicing"; 'data analysis' stays
    # below it on purpose to also exercise the too_small branch)
    phones = []
    for tag, name in [('theory', 'Ana'), ('data analysis', 'Bo'), ('theory', 'Cy'), ('theory', 'Di')]:
        c = Client(); r = c.post(f'/p/{code}/join/', {'expertise_tag': tag, 'display_name': name})
        assert r.status_code == 302; phones.append(c)
    assert staff_client.get('/presentations/example/present/state/').json()['participants'] == 4
    # 3. presenter goes to 'orbits', opens q-orbits; phones see it open and answer
    staff_client.post('/presentations/example/present/goto/', data=json.dumps({'slide': 'orbits'}), content_type='application/json')
    staff_client.post('/presentations/example/present/interaction/q-orbits/open/')
    st = phones[0].get(f'/p/{code}/state/').json()
    assert st['slide'] == 'orbits' and st['interactions']['q-orbits'] == 'open'
    for c, ch in zip(phones, ['B', 'A', 'B', 'B']):
        assert c.post(f'/p/{code}/respond/q-orbits/', data=json.dumps({'choice': ch}), content_type='application/json').status_code == 200
    # 4. distribution + numeric + text round trip
    staff_client.post('/presentations/example/present/interaction/q-prior/open/')
    assert phones[0].post(f'/p/{code}/respond/q-prior/', data=json.dumps({'weights': [1] * 20}), content_type='application/json').status_code == 200
    staff_client.post('/presentations/example/present/interaction/q-rate/open/')
    assert phones[0].post(f'/p/{code}/respond/q-rate/', data=json.dumps({'value': 20, 'err': 5}), content_type='application/json').status_code == 200
    staff_client.post('/presentations/example/present/interaction/q-word/open/')
    assert phones[1].post(f'/p/{code}/respond/q-word/', data=json.dumps({'text': 'chaotic'}), content_type='application/json').status_code == 200
    # 5. reveal on the results slide; slice by expertise
    staff_client.post('/presentations/example/present/goto/', data=json.dumps({'slide': 'orbits-results'}), content_type='application/json')
    staff_client.post('/presentations/example/present/interaction/q-orbits/revealed/')
    agg = phones[0].get(f'/p/{code}/aggregate/q-orbits/?tag=all').json()
    assert agg['counts'] == {'A': 1, 'B': 3, 'C': 0, 'D': 0}
    # 6. a phone comment on a region while live
    r = phones[2].post('/presentations/example/comment/', data=json.dumps({'slide': 'orbits', 'anchor': {'rect': [.5, .1, .3, .3]}, 'body': 'is B precessing?'}), content_type='application/json')
    assert r.status_code == 201 and r.json()['author'] == 'Cy'
    # 7. lock → phones bounce to archive; archive shows frozen aggregates; never-opened stays hidden
    staff_client.post('/presentations/example/present/lock/')
    assert phones[0].get(f'/p/{code}/').status_code == 302
    arch = phones[0].get('/presentations/example/').content.decode()
    data = json.loads(arch.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert data['session']['locked'] and data['interactions']['q-orbits']['state'] == 'revealed'
    assert data['interactions']['q-prior']['state'] == 'revealed'
    a = phones[0].get('/presentations/example/aggregate/q-orbits/?tag=theory').json()
    assert a['n'] == 3 and a['counts']['B'] == 3
    assert phones[0].get('/presentations/example/aggregate/q-orbits/?tag=data%20analysis').json()['too_small']
    # 8. comments persist and later visitors can add more
    listed = Client().get('/presentations/example/comments/').json()['comments']
    assert len(listed) == 1 and listed[0]['slide'] == 'orbits'
    assert Client().post('/presentations/example/comment/', data=json.dumps({'slide': 'posterior', 'anchor': {'anchor': 'posterior-plot'}, 'body': 'nice'}), content_type='application/json').status_code == 201
    assert Comment.visible.count() == 2
