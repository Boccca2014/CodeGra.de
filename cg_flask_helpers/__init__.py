"""Various helpers for flask used in CodeGrade.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import warnings

import flask
import celery
import structlog

logger = structlog.get_logger()
T = t.TypeVar('T')  # pylint: disable=invalid-name


def callback_after_this_request(
    fun: t.Callable[[], object],
) -> t.Callable[[T], T]:
    """Execute a callback after this request without changing the response.

    :param fun: The callback to execute after the current request.
    :returns: The function that will execute after this request that does that
        the response as argument, so this function wraps your given callback.
    """
    if celery.current_task:
        celery.current_task.add_after_task_callback(fun)
        return lambda x: x

    elif flask.has_request_context():

        @flask.after_this_request
        def after(res: flask.Response) -> flask.Response:
            """The entire callback that is executed at the end of the request.
            """
            if res.status_code < 400:
                fun()
            return res

        return after

    else:

        warnings.warn('Running callback now as we are not in flask or celery')
        logger.error(
            'Running callback directly as we are not in flask/celery',
            report_to_sentry=True
        )
        fun()

        return lambda x: x


class EmptyResponse(flask.Response):  # pylint: disable=too-many-ancestors
    """An empty response.

    This is a subtype of :py:class:`werkzeug.wrappers.Response` where the body
    is empty and the status code is always 204.
    """

    def __init__(self, content: str, *args: t.Any, **kwargs: t.Any) -> None:
        # EmptyResponse should always be empty
        assert not content
        # EmptyResponse always has a status of 204
        assert kwargs.get('status') == 204

        super().__init__(content, *args, **kwargs)

    @classmethod
    def make(cls) -> 'EmptyResponse':
        """Create an empty response.
        """
        return cls('', status=204)


make_empty_response = EmptyResponse.make  # pylint: disable=invalid-name
