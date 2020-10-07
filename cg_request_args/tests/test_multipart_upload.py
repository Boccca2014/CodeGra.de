import io

import flask
import pytest

from cg_request_args import (
    AnyValue, MultipartUpload, _Schema, _schema_generator
)


@pytest.mark.parametrize('multiple', [True, False])
def test_generate_schema(schema_mock, multiple):
    parser = MultipartUpload(AnyValue(), 'file_key', multiple)

    with _schema_generator(schema_mock):
        with pytest.raises(_Schema) as exc:
            parser.from_flask()

    assert exc.value.typ == 'multipart/form-data'
    single_file = {'type': 'string', 'format': 'binary'}
    file_type = {
        'type': 'array', 'items': single_file
    } if multiple else single_file
    assert exc.value.schema == {
        'type': 'object',
        'properties': {
            'json': {'type': 'object'},
            'file_key': file_type,
        },
        'required': ['json'],
    }


def test_get_single():
    app = flask.Flask(__name__)

    @app.route('/files', methods=['POST'])
    def get_files():
        json, files = MultipartUpload(AnyValue(), 'file_key',
                                      False).from_flask()
        return str((json, [f.read() for f in files]))

    with app.app_context():
        response = app.test_client().post('/files')
        assert response.get_data(as_text=True) == '(None, [])'

        response = app.test_client().post(
            '/files', data={
                'file_key': (io.BytesIO(b'hello'), 'filename'),
            }
        )
        assert response.get_data(as_text=True) == "(None, [b'hello'])"

        response = app.test_client().post(
            '/files',
            data={
                'file_key': [(io.BytesIO(b'hello'), 'filename'),
                             (io.BytesIO(b'bye'), 'filename2')],
            }
        )
        assert response.get_data(as_text=True) == "(None, [b'hello'])"

        response = app.test_client().post(
            '/files',
            data={
                'file_key': [(io.BytesIO(b'hello'), 'filename'),
                             (io.BytesIO(b'bye'), 'filename2')],
                'file_key1': (io.BytesIO(b'woo'), 'filename3'),
                'json': (io.BytesIO(b'{"key": "jee"}'), 'json'),
            }
        )
        assert response.get_data(
            as_text=True
        ) == "({'key': 'jee'}, [b'hello'])"


def test_get_multiple():
    app = flask.Flask(__name__)

    @app.route('/files', methods=['POST'])
    def get_files():
        json, files = MultipartUpload(AnyValue(), 'file_key',
                                      True).from_flask()
        return str((json, [f.read() for f in files]))

    with app.app_context():
        response = app.test_client().post('/files')
        assert response.get_data(as_text=True) == '(None, [])'

        response = app.test_client().post(
            '/files', data={
                'file_key': (io.BytesIO(b'hello'), 'filename'),
            }
        )
        assert response.get_data(as_text=True) == "(None, [b'hello'])"

        response = app.test_client().post(
            '/files',
            data={
                'file_key': [(io.BytesIO(b'hello'), 'filename'),
                             (io.BytesIO(b'bye'), 'filename2')],
            }
        )
        assert response.get_data(as_text=True) == "(None, [b'hello', b'bye'])"

        response = app.test_client().post(
            '/files',
            data={
                'file_key': [(io.BytesIO(b'hello'), 'filename'),
                             (io.BytesIO(b'bye'), 'filename2')],
                'file_key1': (io.BytesIO(b'woo'), 'filename3'),
                # Empty filename is skipped
                'file_key2': (io.BytesIO(b'woo'), ''),
                'json': (io.BytesIO(b'{"key": "jee"}'), 'json'),
            }
        )
        assert response.get_data(
            as_text=True
        ) == "({'key': 'jee'}, [b'hello', b'bye', b'woo'])"
