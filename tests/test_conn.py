from unittest.mock import MagicMock

import pytest

from PythonPlug.conn import Conn
from PythonPlug.exception import (
    HTTPRequestError,
    HTTPStateError,
    PythonPlugRuntimeError,
)

from .conftest import CustomReceiveAdapter


def test_conn_response(app):
    res = app.test_client.get("/")
    assert res.status_code == 200
    assert app.conn.halted == True
    assert res.content == b"hello"


def test_conn_query_params(app):
    res = app.test_client.get("/?a=foo&b=bar")
    assert app.conn.query_params == {"a": "foo", "b": "bar"}


def test_conn_path(app):
    res = app.test_client.get("/foo")
    assert app.conn.scope.get("path") == "/foo"


def test_request_headers(app):
    res = app.test_client.get("/", headers={"foo": "bar", "host": "example.com"})
    assert app.conn.req_headers.get("host") == "example.com"
    assert app.conn.req_headers.get("foo") == "bar"


def test_http_status(adapter):
    from http import HTTPStatus

    async def plug(conn):
        conn.status = HTTPStatus.OK
        return await conn.send_resp(b"1", halt=True)

    app = adapter(plug)
    res = app.test_client.get("/")
    assert res.status_code == HTTPStatus.OK


def test_other_message_type(echo_plug):

    from asyncio import Future

    app = CustomReceiveAdapter(
        echo_plug,
        messages=[{"type": "other"}, {"type": "http.request", "body": b"111"}],
    )
    res = app.test_client.post("/")
    assert res.content == b"111"


def test_chunked_response(adapter):
    async def chunked(conn):
        async for chunk in conn.body_iter():
            await conn.send_resp(chunk)
        await conn.halt()
        return conn

    app = adapter(chunked)
    body = b"foo" * 100_000
    res = app.test_client.post("/", data=body)
    assert res.content == body


def test_chunked_request(adapter):
    import requests

    async def plug(conn):
        async for chunk in conn.body_iter():
            await conn.send_resp(chunk)
        await conn.halt()
        return conn

    def body():
        yield b"1" * 100
        yield b"2" * 100

    app = adapter(plug)
    res = app.test_client.post("/", data=body())
    assert res.content == b"1" * 100 + b"2" * 100


def test_redirect(adapter):
    async def redirect(conn):
        return await conn.redirect("/foo")

    app = adapter(redirect)
    body = b"foo" * 100_000
    res = app.test_client.post("/", data=body)
    assert res.status_code == 302


def test_body_after_body_iter(adapter):
    import requests

    async def plug(conn):
        async for chunk in conn.body_iter():
            await conn.send_resp(chunk)
        async for chunk in conn.body_iter():
            await conn.send_resp(chunk)
        await conn.halt()
        return conn

    def body():
        yield b"1" * 100
        yield b"2" * 100

    app = adapter(plug)
    res = app.test_client.post("/", data=body())
    assert res.content == (b"1" * 100 + b"2" * 100) * 2


def test_file_request(adapter):
    # this does not test parsing
    from io import BytesIO

    async def plug(conn):
        body = await conn.body()
        await conn.send_resp(body, halt=True)
        return conn

    app = adapter(plug)
    body = BytesIO(b"1" * 100)
    res = app.test_client.post("/", files=[("file", body)])
    assert (b"1" * 100) in res.content


def test_body_consumption(adapter):
    async def plug(conn):
        await conn.send_resp((await conn.body()) + (await conn.body()), halt=True)
        return conn

    app = adapter(plug)
    body = b"foo" * 100_000
    res = app.test_client.post("/", data=body)
    assert res.content == body * 2


def test_request_cookie(adapter):
    async def plug(conn):
        import json

        await conn.send_resp(json.dumps(conn.req_cookies_dict).encode(), halt=True)
        return conn

    app = adapter(plug)
    res = app.test_client.get("/", cookies={"foo": "bar"})
    assert res.json() == {"foo": "bar"}


def test_response_cookie(adapter):
    async def plug(conn):
        conn.put_resp_cookie("foo", "bar", secure=True)
        conn.put_resp_cookie("hello", "foo", path="/test")
        await conn.halt()

    app = adapter(plug)
    res = app.test_client.get("/")
    cookies = app.test_client.cookies
    assert cookies.get_dict() == {"foo": "bar", "hello": "foo"}
    assert set(cookies.list_paths()) == {"/", "/test"}


# test exceptions
def test_request_type_exception(echo_app):

    with pytest.raises(HTTPRequestError):
        echo_app.test_client.websocket_connect("/")


def test_wrong_content_length(echo_app):
    # this does not test parsing
    from io import BytesIO, BufferedReader
    import requests

    def body():
        data = BufferedReader(BytesIO(b"1" * 100), 10)
        chunk = data.read(1)
        while chunk:
            yield chunk
            chunk = data.read(1)

    prepared = requests.Request("POST", "http://testserver/", data=body()).prepare()
    with pytest.raises(HTTPRequestError):
        # Normal clients won't do this, and this is not valid HTTP bahaviour
        # but it serves the purpose to test PythonPlug
        prepared.headers["content-length"] = "1"
        prepared.headers["Expect"] = "100-continue"
        prepared.headers["Transfer-Encoding"] = "identity"
        echo_app.test_client.send(prepared)


def test_non_bytes_body(echo_app):
    with pytest.raises(PythonPlugRuntimeError):
        import os

        echo_app.test_client.post("/", data=os)


def test_client_disconnect(echo_plug):

    app = CustomReceiveAdapter(echo_plug, messages=[{"type": "http.disconnect"}])

    with pytest.raises(HTTPRequestError):
        app.test_client.post("/")


def test_send_after_halted(adapter):
    async def plug(conn):
        await conn.send_resp(b"foo", halt=True)
        await conn.send_resp(b"bar", halt=True)

    app = adapter(plug)
    with pytest.raises(HTTPStateError):
        app.test_client.get("/")


def test_change_state_after_started(adapter):
    async def plug(conn):
        conn.status = 201
        await conn.start_resp()
        await conn.send_resp(b"bar", status=200, halt=True)

    app = adapter(plug)
    with pytest.raises(HTTPStateError):
        app.test_client.get("/")


def test_redirect_after_started(adapter):
    async def plug(conn):
        await conn.start_resp()
        await conn.redirect("/foo")

    app = adapter(plug)
    with pytest.raises(HTTPStateError):
        app.test_client.get("/")


def test_halt_after_halt(adapter):
    async def plug(conn):
        await conn.start_resp()
        await conn.halt()
        await conn.halt()

    app = adapter(plug)
    with pytest.raises(HTTPStateError):
        app.test_client.get("/")


def test_not_plugged(adapter, echo_plug):
    import asyncio

    conn = Conn(scope={})

    async def send():
        await conn.send(b"foo")

    async def receive():
        await conn.receive(b"foo")

    loop = asyncio.get_event_loop()
    with pytest.raises(HTTPStateError):
        loop.run_until_complete(send())
    with pytest.raises(HTTPStateError):
        loop.run_until_complete(receive())


def test_multiple_body_iter(adapter):
    import requests

    async def plug(conn):
        async for chunk in conn.body_iter():
            async for c in conn.body_iter():
                await conn.send_resp(chunk)
        await conn.halt()
        return conn

    def body():
        yield b"1" * 100
        yield b"2" * 100

    app = adapter(plug)
    with pytest.raises(HTTPStateError):
        res = app.test_client.post("/", data=body())


def test_after_start_callback(adapter):
    mock = MagicMock()

    async def cb(conn):
        mock(conn)

    async def plug(conn: Conn):
        conn.register_after_start(cb)
        await conn.send_resp(b"", halt=True)

    app = adapter(plug)
    mock.assert_not_called()
    app.test_client.get("/")
    mock.assert_called_once()


def test_after_send_callback(adapter):
    mock = MagicMock()

    async def cb(conn):
        mock(conn)

    async def plug(conn: Conn):
        conn.register_after_send(cb)
        await conn.send_resp(b"", halt=True)

    app = adapter(plug)
    mock.assert_not_called()
    app.test_client.get("/")
    mock.assert_called_once()


def test_call_asgi_app(adapter):
    class Application:
        def __init__(self, scope):
            self.scope = scope

        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"foo"})

    async def plug(conn: Conn):
        await conn.call_asgi_app(Application)

    app = adapter(plug)
    res = app.test_client.get("/")
    assert res.content == b"foo"
    assert app.conn.halted == True
