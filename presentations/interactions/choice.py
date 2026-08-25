from .base import Interaction


class Choice(Interaction):
    name = 'choice'
    config_schema = {
        'type': 'object', 'required': ['prompt', 'options'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'options': {'type': 'array', 'minItems': 2, 'maxItems': 8, 'items': {'type': 'string'}},
            'answer': {'type': 'string'},
        },
    }
    payload_schema = {'type': 'object', 'required': ['choice'], 'properties': {'choice': {'type': 'string'}}}

    def extra_config_checks(self, config):
        if 'answer' in config and config['answer'] not in config['options']:
            raise ValueError('choice config: answer must be one of options')

    def normalise(self, payload, config):
        if payload['choice'] not in config['options']:
            raise ValueError('choice not in options')
        return {'choice': payload['choice']}

    def aggregate(self, payloads, config):
        counts = {o: 0 for o in config['options']}
        for p in payloads:
            if p.get('choice') in counts:
                counts[p['choice']] += 1
        return {'n': len(payloads), 'counts': counts}
