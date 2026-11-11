"""Strict JSON shared by HTTP and the privileged local protocol."""
import json


def loads(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('invalid_json_number')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)
