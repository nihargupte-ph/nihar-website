import statistics

from .base import Interaction


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    pos = (len(sorted_vals) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


class Numeric(Interaction):
    name = 'numeric'
    config_schema = {
        'type': 'object', 'required': ['prompt'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'log': {'type': 'boolean'},
            'min': {'type': 'number'}, 'max': {'type': 'number'},
            'truth': {'type': 'number'}, 'unit': {'type': 'string'},
        },
    }
    payload_schema = {'type': 'object', 'required': ['value'],
                      'properties': {'value': {}, 'err': {}}}

    @staticmethod
    def _num(v, what):
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f'{what} must be a number')
        if f != f or f in (float('inf'), float('-inf')):
            raise ValueError(f'{what} must be finite')
        return f

    def normalise(self, payload, config):
        value = self._num(payload['value'], 'value')
        if config.get('log') and value <= 0:
            raise ValueError('value must be > 0 on a log scale')
        if 'min' in config and value < config['min']:
            raise ValueError('value below min')
        if 'max' in config and value > config['max']:
            raise ValueError('value above max')
        out = {'value': value}
        if payload.get('err') not in (None, ''):
            err = self._num(payload['err'], 'err')
            if err < 0:
                raise ValueError('err must be >= 0')
            out['err'] = err
        return out

    def aggregate(self, payloads, config):
        values = sorted(float(p['value']) for p in payloads if 'value' in p)
        errs = [p.get('err') for p in payloads if 'value' in p]
        return {
            'n': len(values), 'values': values, 'errs': errs,
            'median': statistics.median(values) if values else None,
            'q16': _quantile(values, 0.16), 'q84': _quantile(values, 0.84),
        }
