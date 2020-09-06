import flask
import pytest

from cg_enum import CGEnum, named_equally
from cg_json import JSONResponse


def test_is_method():
    class Enum(CGEnum):
        b = 1
        c = 2

    assert Enum.c.is_c is True
    assert Enum.c.is_b is False

    with pytest.raises(AttributeError):
        Enum.c.is_e

    with pytest.raises(AttributeError):
        Enum.c.not_a_prop


def test_jsonify():
    class Enum(CGEnum):
        name_a = 2
        name_b = 3

    with flask.Flask(__name__).app_context():
        assert JSONResponse.dump_to_object(Enum.name_a) == 'name_a'
        assert JSONResponse.dump_to_object(Enum.name_b) == 'name_b'


def test_name_equally():
    class EnumOK(CGEnum):
        name_a = 'name_a'
        name_b = 'name_b'

    assert named_equally(EnumOK) is EnumOK

    class EnumMisspell(CGEnum):
        name_a = 'name_a'
        name_b = 'namee_b'

    with pytest.raises(ValueError):
        named_equally(EnumMisspell)

    class EnumDups(CGEnum):
        name_a = 'name_a'
        name_b = 'name_a'

    with pytest.raises(ValueError):
        named_equally(EnumDups)
