import hashlib
import re

import bleach
import markdown as md
from django.conf import settings

_ALLOWED_TAGS = ['p', 'em', 'strong', 'code', 'pre', 'a', 'ul', 'ol', 'li', 'blockquote', 'br', 'h3', 'h4']
_ALLOWED_ATTRS = {'a': ['href', 'title', 'rel', 'target']}
_STOPWORDS = set('a an the and or of to in on for is are it its this that with as at by from be'.split())
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")


def _link_attrs(attrs, new=False):
    attrs[(None, 'rel')] = 'nofollow noopener'
    attrs[(None, 'target')] = '_blank'
    return attrs


def render_markdown(text):
    html = md.markdown(text or '', extensions=['nl2br'])
    cleaned = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
    return bleach.linkify(cleaned, callbacks=[_link_attrs], skip_tags=['pre', 'code'])


def hash_ip(ip):
    return hashlib.sha256((settings.SECRET_KEY + (ip or '')).encode()).hexdigest()


def tokenize_words(text):
    return [w for w in _WORD_RE.findall((text or '').lower()) if w not in _STOPWORDS]
