from .base import Interaction


class Distribution(Interaction):
    name = 'distribution'
    config_schema = {
        'type': 'object', 'required': ['prompt', 'axis'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'axis': {
                'type': 'object', 'required': ['min', 'max', 'bins'], 'additionalProperties': False,
                'properties': {
                    'min': {'type': 'number'}, 'max': {'type': 'number'},
                    'bins': {'type': 'integer', 'minimum': 2, 'maximum': 100},
                    'label': {'type': 'string'}, 'log': {'type': 'boolean'},
                },
            },
        },
    }
    payload_schema = {'type': 'object', 'required': ['weights'],
                      'properties': {'weights': {'type': 'array', 'items': {'type': 'number'}}}}

    def extra_config_checks(self, config):
        if config['axis']['max'] <= config['axis']['min']:
            raise ValueError('distribution config: axis.max must exceed axis.min')

    def normalise(self, payload, config):
        bins = config['axis']['bins']
        w = [float(x) for x in payload['weights']]
        if len(w) != bins:
            raise ValueError(f'weights must have {bins} entries')
        if any(x < 0 for x in w):
            raise ValueError('weights must be >= 0')
        total = sum(w)
        if total <= 0:
            raise ValueError('weights must not be all zero')
        return {'weights': [x / total for x in w]}

    @staticmethod
    def edges(config):
        a = config['axis']
        return [a['min'] + (a['max'] - a['min']) * i / a['bins'] for i in range(a['bins'] + 1)]

    def aggregate(self, payloads, config):
        bins = config['axis']['bins']
        curves = [p['weights'] for p in payloads if len(p.get('weights', [])) == bins]
        mean = [sum(c[i] for c in curves) / len(curves) for i in range(bins)] if curves else [0.0] * bins
        return {'n': len(curves), 'mean': mean, 'curves': curves, 'edges': self.edges(config)}
