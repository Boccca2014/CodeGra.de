import pytest
import structlog

from cg_request_args import (
    AnyValue, logger, _Schema, _ParserLike, _schema_generator
)


def test_ref_and_description(schema_mock):
    use_ref = True

    class _MyParser(AnyValue):
        def _to_open_api(self, schema):
            if use_ref:
                return {'$ref': 'placeholder'}
            return super()._to_open_api(schema)

    assert _MyParser().to_open_api(schema_mock) == {'$ref': 'placeholder'}
    assert _MyParser().add_description('desc').to_open_api(schema_mock) == {
        'description': ('Comment', 'desc'), 'allOf': [{'$ref': 'placeholder'}]
    }
    use_ref = False
    assert _MyParser().to_open_api(schema_mock) == {'type': 'object'}
    assert _MyParser().add_description('desc').to_open_api(schema_mock) == {
        'description': ('Comment', 'desc'), 'type': 'object'
    }
    use_ref = True

    with _schema_generator(schema_mock):
        with pytest.raises(_Schema) as exc:
            _MyParser().from_flask()
    assert exc.value.schema == {'$ref': 'placeholder'}
    assert exc.value.typ == 'application/json'


def test_parse_and_log(monkeypatch):
    logs = []

    def set_log(*args, **kwargs):
        logs.append((*args, kwargs))

    parser = AnyValue()
    monkeypatch.setattr(logger, 'info', set_log)

    parser.try_parse_and_log(None, log_replacer=lambda _, __: 'NOPE')
    assert logs[0][0] == 'JSON request processed'
    assert logs[0][-1]['request_data'] == '<FILTERED>'
    assert logs[0][-1]['request_data_type'] == 'null'
    logs.clear()

    parser.try_parse_and_log(
        {'password': 'hunter2', 'other': 'woo'},
        log_replacer=lambda k, v: '<REDACTED>' if k == 'password' else v
    )
    assert logs[0][0] == 'JSON request processed'
    assert logs[0][-1]['request_data'] == {
        'password': '<REDACTED>', 'other': 'woo'
    }
    logs.clear()

    parser.try_parse_and_log({'password': 'hunter2', 'other': 'woo'})
    assert logs[0][-1]['request_data'] == {
        'password': 'hunter2', 'other': 'woo'
    }
