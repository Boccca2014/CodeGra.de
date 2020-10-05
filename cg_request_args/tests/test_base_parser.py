import pytest

from cg_request_args import AnyValue, _Schema, _ParserLike, _schema_generator


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
