from datetime import datetime, timedelta

from psef import helpers
from psef.models import Assignment


def test_deadline_expired_property(monkeypatch):
    a = Assignment(deadline=None, is_lti=False, course=None)
    assert not a.deadline_expired

    before = datetime.utcnow()
    monkeypatch.setattr(helpers, 'get_request_start_time', datetime.utcnow)

    a.deadline = before
    assert a.deadline_expired

    a.deadline = datetime.utcnow() + timedelta(hours=1)
    assert not a.deadline_expired


def test_eq_of_assignment():
    def make(id=None):
        a = Assignment(course=None, is_lti=False)
        a.id = id
        return a

    assert make() != object()
    assert make(id=5) != make(id=6)
    assert make(id=5) == make(id=5)
