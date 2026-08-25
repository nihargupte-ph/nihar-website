import jsonschema


class Interaction:
    name = ''
    config_schema = {'type': 'object'}
    payload_schema = {'type': 'object'}

    def validate_config(self, config):
        try:
            jsonschema.validate(config, self.config_schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f'{self.name} config: {e.message}')
        self.extra_config_checks(config)

    def extra_config_checks(self, config):
        pass

    def clean_payload(self, payload, config):
        if not isinstance(payload, dict):
            raise ValueError('payload must be an object')
        try:
            jsonschema.validate(payload, self.payload_schema)
        except jsonschema.ValidationError as e:
            raise ValueError(e.message)
        return self.normalise(payload, config)

    def normalise(self, payload, config):
        return payload

    def aggregate(self, payloads, config):
        raise NotImplementedError
