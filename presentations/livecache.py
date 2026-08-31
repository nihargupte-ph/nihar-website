"""Per-process cache: each of the 3 gunicorn workers keeps its own copy, so a worker that missed an
invalidate() serves state at most TTL seconds stale and then self-heals on the next rebuild."""
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
