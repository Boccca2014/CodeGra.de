import os
import json
import socket
import typing as t
import tempfile
import contextlib
import multiprocessing

import jwt
import urllib3
import requests
import structlog

import psef
import cg_json
import cg_request_args as rqa
from cg_helpers import assert_never

logger = structlog.get_logger()

_COMMENT_PARSER = rqa.Lazy(
    lambda: rqa.BaseFixedMapping.from_typeddict(
        psef.models.AutoTestQualityComment.InputAsJSON,
    )
)

_INPUT_PARSER = rqa.Union(
    rqa.FixedMapping(
        rqa.RequiredArgument(
            'op', rqa.StringEnum('put_comment'), 'Put a new comment'
        ),
        rqa.RequiredArgument('comment', _COMMENT_PARSER, 'The new comment'),
    ),
    rqa.FixedMapping(
        rqa.RequiredArgument(
            'op', rqa.StringEnum('put_comments'), 'Put new comments'
        ),
        rqa.RequiredArgument(
            'comments', rqa.List(_COMMENT_PARSER), 'The new comment'
        ),
    ),
)

NETWORK_EXCEPTIONS = (
    requests.RequestException, ConnectionError, urllib3.exceptions.HTTPError
)

SOCKET_NAME = 'cg.socket'


def _send_reseponse(
    conn: socket.socket, message: str, ok: bool, rest: t.Mapping[str, t.Any]
) -> None:
    conn.sendall(
        json.dumps({
            **rest, 'message': message,
            'ok': ok
        }).encode('utf8')
    )


class APIHandler:
    def __init__(
        self,
        sock_dir: str,
        get_session: t.Callable[[], requests.Session],
        base_url: str,
    ) -> None:
        self._sock_dir = sock_dir
        self._started = multiprocessing.Event()
        self._stop = multiprocessing.Event()
        self._finished = multiprocessing.Event()
        self._get_session = get_session
        self._result_id = multiprocessing.Value('q', 0)
        self._base_url = base_url
        self._cur_step_id = multiprocessing.Value('q', 0)

    def stop(self) -> None:
        self._stop.set()
        self._finished.wait()

    @property
    def socket_file(self) -> str:
        return os.path.join(self._sock_dir, SOCKET_NAME)

    def set_result_id(self, result_id: int) -> None:
        self._result_id.value = result_id

    def set_step_id(self, step_id: int) -> None:
        self._cur_step_id.value = step_id

    @classmethod
    @contextlib.contextmanager
    def running_handler(
        cls,
        get_session: t.Callable[[], requests.Session],
        base_url: str,
    ) -> t.Generator['APIHandler', None, None]:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o777)

            self = cls(tmpdir, get_session, base_url=base_url)
            proc = multiprocessing.Process(target=self.run, args=tuple())
            proc.start()
            self._started.wait()
            try:
                yield self
            finally:
                self.stop()
                proc.join()

    def run(self) -> None:
        self._stop.clear()
        self._finished.clear()

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        socket_file = self.socket_file
        sock.bind(socket_file)
        os.chmod(socket_file, 0o777)
        sock.listen()
        sock.settimeout(1.0)

        self._started.set()

        try:
            while not self._stop.is_set():
                try:
                    conn, _ = sock.accept()
                except:
                    continue

                try:
                    conn.settimeout(10.0)
                    self._handle_conn(
                        conn, self._result_id.value, self._cur_step_id.value
                    )
                except:
                    logger.error('could not send comments', exc_info=True)
                    _send_reseponse(
                        conn, 'Something unknown went wrong', False, {}
                    )
                finally:
                    conn.close()
        finally:
            logger.info('Stop is set!')
            sock.close()
            self._finished.set()

    def _handle_conn(
        self, conn: socket.socket, result_id: int, step_id: int
    ) -> None:
        data = b''
        while True:
            new_data = conn.recv(4096)
            data += new_data
            if b'\0' in new_data:
                break

        try:
            request = _INPUT_PARSER.try_parse(
                json.loads(data.split(b'\0')[0].decode())
            )
        except (rqa.SimpleParseError, rqa.MultipleParseErrors) as exc:
            conn.send(
                json.dumps({
                    'message': 'Parsing failed',
                    **exc.to_dict()
                }).encode('utf8')
            )
            return
        except ValueError:
            _send_reseponse(
                conn, 'Could not parse message', False,
                {'received': str(data)}
            )
            return

        if request.op == 'put_comment':
            result = self._put_comments(result_id, step_id, [request.comment])
        elif request.op == 'put_comments':
            result = self._put_comments(result_id, step_id, request.comments)
        else:
            assert_never(request.op)

        _send_reseponse(conn, *result, rest={})

    def _put_comments(
        self,
        result_id: int,
        step_id: int,
        comments: t.Sequence['psef.models.AutoTestQualityComment.InputAsJSON'],
    ) -> t.Tuple[str, bool]:
        ses = self._get_session()
        try:
            ses.post(
                (
                    f'{self._base_url}/results/{result_id}/steps/'
                    f'{step_id}/quality_comments/'
                ),
                data=json.dumps(comments, cls=cg_json.CustomJSONEncoder),
                headers={'Content-Type': 'application/json'}
            ).raise_for_status()
        except NETWORK_EXCEPTIONS as exc:
            return ('Could not send comments', False)
        return ('Comments uploaded', True)
