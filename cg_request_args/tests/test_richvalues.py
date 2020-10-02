import pytest

from cg_request_args import RichValue, SimpleParseError


@pytest.mark.parametrize('ok,value', [
    (False, 5),
    (False, 'not_an_email'),
    (False, '@codegrade.com'),
    (False, 'Thomas Schaper <>'),
    (False, 'Thomas Schaper <valid@codegrade.com>; noemail'),
    (True, 'thomas@codegrade.com'),
    (True, 'Thomas Schaper <valid@codegrade.com>'),
    (True, 'Thomas Schaper <valid@codegrade.com>, valid2@codegrade.com'),
])
def test_email_list(ok, value):
    parser = RichValue.EmailList

    if ok:
        assert parser.try_parse(value) == value
    else:
        with pytest.raises(SimpleParseError):
            parser.try_parse(5)
