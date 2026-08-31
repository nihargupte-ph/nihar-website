"""An audience-drawn prior on a log10(e) grid, with who-drew-it metadata per curve.

Payload weights are bin masses (sum 1). `aggregate` returns every curve with its
metadata (name / institute / expertise tags) so the presenter can hover and filter,
the unweighted mean, and two reference priors on the same grid: log-uniform on
[10^log_uniform_min, 10^max] (default: the whole axis) and uniform in e on [10^min, 10^max].
"""
from .base import Interaction

EXPERTISE = ['data analysis', 'waveform model', 'theoretical modelling', 'numerical relativity',
             'astrophysics', 'instrumentation', 'other']


class Prior(Interaction):
    name = 'prior'
    config_schema = {
        'type': 'object', 'required': ['prompt', 'axis'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'axis': {
                'type': 'object', 'required': ['min', 'max', 'bins'], 'additionalProperties': False,
                'properties': {
                    'min': {'type': 'number'}, 'max': {'type': 'number'},
                    'bins': {'type': 'integer', 'minimum': 2, 'maximum': 200},
                    'label': {'type': 'string'},
                },
            },
            'log_uniform_min': {'type': 'number'},
        },
    }
    payload_schema = {
        'type': 'object', 'required': ['weights'],
        'properties': {
            'weights': {'type': 'array', 'items': {'type': 'number'}},
            'name': {'type': 'string', 'maxLength': 60},
            'institute': {'type': 'string', 'maxLength': 80},
            'expertise': {'type': 'array', 'items': {'type': 'string', 'enum': EXPERTISE}, 'uniqueItems': True},
            'other': {'type': 'string', 'maxLength': 60},
        },
    }

    def extra_config_checks(self, config):
        a = config['axis']
        if a['max'] <= a['min']:
            raise ValueError('prior config: axis.max must exceed axis.min')
        lo = config.get('log_uniform_min', a['min'])
        if not a['min'] <= lo < a['max']:
            raise ValueError('prior config: log_uniform_min must lie inside the axis')

    def normalise(self, payload, config):
        bins = config['axis']['bins']
        w = payload['weights']
        if any(isinstance(x, bool) for x in w):
            raise ValueError('weights must be numbers')
        w = [float(x) for x in w]
        if len(w) != bins:
            raise ValueError(f'weights must have {bins} entries')
        if any(x != x or x in (float('inf'), float('-inf')) for x in w):
            raise ValueError('weights must be finite')
        if any(x < 0 for x in w):
            raise ValueError('weights must be >= 0')
        total = sum(w)
        if total <= 0:
            raise ValueError('weights must not be all zero')
        return {
            'weights': [x / total for x in w],
            'name': payload.get('name', '').strip(),
            'institute': payload.get('institute', '').strip(),
            'expertise': [t for t in EXPERTISE if t in payload.get('expertise', [])],
            'other': payload.get('other', '').strip(),
        }

    @staticmethod
    def edges(config):
        a = config['axis']
        return [a['min'] + (a['max'] - a['min']) * i / a['bins'] for i in range(a['bins'] + 1)]

    def comparisons(self, config):
        a = config['axis']
        bins = a['bins']
        edges = self.edges(config)
        lo = config.get('log_uniform_min', a['min'])
        # log-uniform: mass ∝ the overlap of each bin with [lo, max] in log10 e
        overlap = [max(0.0, min(edges[i + 1], a['max']) - max(edges[i], lo)) for i in range(bins)]
        e = [10.0 ** x for x in edges]
        span = e[-1] - e[0]
        return {
            'log_uniform': [o / (a['max'] - lo) for o in overlap],
            'uniform': [(e[i + 1] - e[i]) / span for i in range(bins)],
        }

    def aggregate(self, payloads, config):
        bins = config['axis']['bins']
        curves = [p for p in payloads if len(p.get('weights', [])) == bins]
        mean = [sum(c['weights'][i] for c in curves) / len(curves) for i in range(bins)] if curves else [0.0] * bins
        return {'n': len(curves), 'mean': mean, 'curves': curves, 'edges': self.edges(config),
                'expertise': EXPERTISE, 'comparisons': self.comparisons(config)}
