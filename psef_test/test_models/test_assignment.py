from datetime import datetime, timedelta

import pytest

from psef import helpers, exceptions
from psef.models import Course, Assignment


def test_deadline_expired_property(monkeypatch):
    course = Course(id=5)
    a = Assignment(deadline=None, is_lti=False, course=course)
    assert not a.deadline_expired

    before = datetime.utcnow()
    monkeypatch.setattr(helpers, 'get_request_start_time', datetime.utcnow)

    a.deadline = before
    assert a.deadline_expired

    a.deadline = datetime.utcnow() + timedelta(hours=1)
    assert not a.deadline_expired


def test_eq_of_assignment():
    def make(id=None):
        course = Course(id=5)
        a = Assignment(course=course, is_lti=False)
        a.id = id
        return a

    assert make() != object()
    assert make(id=5) != make(id=6)
    assert make(id=5) == make(id=5)


def test_update_cgignore_invalid():
    course = Course(id=5)
    a = Assignment(deadline=None, is_lti=False, course=course)
    with pytest.raises(exceptions.APIException):
        a.update_cgignore('invalid', 'err')

    with pytest.raises(exceptions.APIException):
        a.update_cgignore('IgnoreFilterManager', ['not a string'])

    with pytest.raises(exceptions.APIException):
        a.update_cgignore('SubmissionValidator', 'not a dict')


def test_update_amount_in_cool_off_period_invalid():
    course = Course(id=5)
    a = Assignment(deadline=None, is_lti=False, course=course)
    with pytest.raises(exceptions.APIException):
        a.amount_in_cool_off_period = 0

    with pytest.raises(exceptions.APIException):
        a.amount_in_cool_off_period = -1

    a.amount_in_cool_off_period = 1


def test_max_submissions_invalid():
    course = Course(id=5)
    a = Assignment(deadline=None, is_lti=False, course=course)
    with pytest.raises(exceptions.APIException):
        a.max_submissions = 0

    with pytest.raises(exceptions.APIException):
        a.max_submissions = -1
