from collections import Counter

from ..textutil import tokenize_words
from .base import Interaction

_BLOCKLIST = {'fuck', 'shit', 'cunt', 'nigger', 'faggot', 'bitch', 'asshole'}


class Text(Interaction):
    name = 'text'
    config_schema = {
        'type': 'object', 'required': ['prompt'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'max_len': {'type': 'integer', 'minimum': 1, 'maximum': 80},
        },
    }
    payload_schema = {'type': 'object', 'required': ['text'], 'properties': {'text': {'type': 'string'}}}

    def normalise(self, payload, config):
        text = ' '.join(payload['text'].split())
        max_len = config.get('max_len', 80)
        if not text:
            raise ValueError('text is empty')
        if len(text) > max_len:
            raise ValueError(f'text longer than {max_len} characters')
        if set(tokenize_words(text)) & _BLOCKLIST:
            raise ValueError('text rejected')
        return {'text': text}

    def aggregate(self, payloads, config):
        counts = Counter()
        for p in payloads:
            counts.update(set(tokenize_words(p.get('text', ''))))
        return {'n': len(payloads), 'counts': dict(counts.most_common(60))}
