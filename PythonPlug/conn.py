from http import HTTPStatus
from http.cookies import SimpleCookie
from operator import itemgetter
from typing import List, Optional, Union
from urllib.parse import parse_qsl

from multidict import CIMultiDict

from .exception import HTTPRequestError, HTTPStateError, PythonPlugRuntimeError
from .typing import CoroutineFunction


class Conn:  # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        *,
        scope: dict,
        receive: Optional[CoroutineFunction] = None,
        send: Optional[CoroutineFunction] = None
    ) -> None:

        self._receive = receive
        self._send = send

        # request fields
        self._scope = scope
        self._req_headers: Optional[CIMultiDict] = None
        self._req_cookies: SimpleCookie = SimpleCookie()
        self.http_body = b""
        self.http_has_more_body = True
        self.http_received_body_length = 0

        # response fields
        self.resp_charset: str = "utf-8"
        self.resp_cookies: SimpleCookie = SimpleCookie()
        self.resp_headers: CIMultiDict = CIMultiDict()
        self.status: Union[int, HTTPStatus] = 0

        # conn fields
        self.halted = False
        self.started = False

        # private fields
        self.private: dict = {}

        # hooks
        self._after_start: List[CoroutineFunction] = []
        self._before_send: List[CoroutineFunction] = []
        self._after_send: List[CoroutineFunction] = []

    @property
    def req_headers(self) -> CIMultiDict:
        if not self._req_headers:
            self._req_headers = CIMultiDict(
                [
                    (k.decode("ascii"), v.decode("ascii"))
                    for (k, v) in self._scope["headers"]
                ]
            )
        return self._req_headers

    @property
    def req_cookies(self) -> SimpleCookie:
        if not self._req_headers:
            self._req_cookies.load(self.req_headers.get("cookie", {}))
        return self._req_cookies

    @property
    def req_cookies_dict(self):
        return {key: m.value for key, m in self.req_cookies.items()}

    @property
    def scope(self):
        return self._scope

    @property
    def type(self):
        return self.scope.get("type")

    @property
    def query_params(self):
        return CIMultiDict(
            parse_qsl(self.scope.get("query_string", b"").decode("utf-8"))
        )

    async def send(self, message, *args, **kwargs):
        if not self._send:
            raise HTTPStateError("Conn is not plugged.")
        await self._send(message, *args, **kwargs)
        if not self.started and message.get("type") == "http.response.start":
            self.started = True
            for callback in self._after_start:
                await callback(self)
        if (
            not self.halted
            and message.get("type") == "http.response.body"
            and message.get("more_body", False) is False
        ):
            self.halted = True
            for callback in self._after_send:
                await callback(self)
        return self

    async def receive(self, *args, **kwargs):
        if not self._receive:
            raise HTTPStateError("Conn is not plugged.")
        return await self._receive(*args, **kwargs)

    async def body_iter(self, save=True):
        if not self.type == "http":
            raise HTTPRequestError("Request is not HTTP")
        if self.http_received_body_length > 0 and self.http_has_more_body:
            raise HTTPStateError("body iter is already started and is not finished")
        if self.http_received_body_length > 0 and not self.http_has_more_body:
            yield self.http_body
        req_body_length = (
            int(self.req_headers.get("content-length", "0"))
            if not self.req_headers.get("transfer-encoding") == "chunked"
            else None
        )
        while self.http_has_more_body:
            if req_body_length and self.http_received_body_length > req_body_length:
                raise HTTPRequestError("body is longer than declared")
            message = await self.receive()
            message_type = message.get("type")
            await self.handle_message(message)
            if message_type != "http.request":
                continue
            chunk = message.get("body", b"")
            if not isinstance(chunk, bytes):
                raise PythonPlugRuntimeError("Chunk is not bytes")
            if save:
                self.http_body += chunk
            self.http_has_more_body = message.get("more_body", False) or False
            self.http_received_body_length += len(chunk)
            yield chunk

    async def body(self):
        return b"".join([chunks async for chunks in self.body_iter()])

    async def handle_message(self, message):
        if message.get("type") == "http.disconnect":
            raise HTTPRequestError("Disconnected")

    def put_resp_header(self, key, value):
        self.resp_headers.add(key, value)
        return self

    def put_resp_cookie(self, key, value, **params):
        self.resp_cookies[key] = value
        for k, v in params.items():
            self.resp_cookies[key][k] = v
        return self

    async def send_resp(
        self,
        body: bytes,
        status: Optional[Union[int, HTTPStatus]] = None,
        halt: bool = False,
    ):
        if self.halted:
            raise HTTPStateError("Connection already halted")
        if self.started and status and status != self.status:
            raise HTTPStateError("Cannot change status code after response started")
        if not self.started:
            if status:
                self.status = status
            if halt:
                self.put_resp_header("content-length", str(len(body)))
            await self.start_resp()
        await self.send(
            {"type": "http.response.body", "body": body or b"", "more_body": True}
        )
        if halt:
            await self.halt()
        return self

    async def start_resp(self):
        self.status = self.status or 200
        if isinstance(self.status, HTTPStatus):
            self.status = self.status.value
        headers = [
            [k.encode("ascii"), v.encode("ascii")] for k, v in self.resp_headers.items()
        ]
        for value in self.resp_cookies.values():
            headers.append([b"Set-Cookie", value.OutputString().encode("ascii")])
        await self.send(
            {"type": "http.response.start", "status": self.status, "headers": headers}
        )
        return self

    async def halt(self):
        if self.halted:
            raise HTTPStateError("Conn already halted")
        if not self.started:
            self.status = 204
            await self.start_resp()
        await self.send({"type": "http.response.body", "body": b"", "more_body": False})
        return self

    async def redirect(self, location, code=None, body=b""):
        if self.started:
            raise HTTPStateError("http response already started")
        self.put_resp_header("location", location)
        self.status = code or 302
        await self.send_resp(body, halt=True)
        return self

    async def call_asgi_app(self, asgi_app):
        await asgi_app(self.scope)(self.receive, self.send)
        return self

    def register_after_send(self, callback):
        self._after_send.append(callback)

    def register_after_start(self, callback):
        self._after_start.append(callback)

    def __getattr__(self, name):
        try:
            return itemgetter(name)(self.private)
        except KeyError:
            return None
