import time

TTL = 1.0
_store = {}   # code -> (expires_at, payload)


def get_state(code, builder):
    now = time.monotonic()
    hit = _store.get(code)
    if hit and hit[0] > now:
        return hit[1]
    payload = builder()
    _store[code] = (now + TTL, payload)
    return payload


def invalidate(code):
    _store.pop(code, None)
