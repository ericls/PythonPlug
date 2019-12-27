from asyncio import Future

import pytest
from starlette.testclient import TestClient

from PythonPlug.adapter import ASGIAdapter
from PythonPlug.conn import ConnWithWS


class TestAdapter(ASGIAdapter):
    ConnClass = ConnWithWS

    def __init__(self, plug) -> None:
        super().__init__(plug)
        self.test_client = TestClient(self)


class Receiver:
    def __init__(self, messages):
        self.messages = messages

    def __call__(self):
        if self.messages:
            m = self.messages.pop(0)
            f = Future()
            f.set_result(m)
            return f
        else:
            f = Future()
            f.set_result(b"")
            return f


class CustomReceiveAdapter(TestAdapter):
    def __init__(self, plug, messages):
        super().__init__(plug)
        self.receiver = Receiver(messages)
        self.ConnClass = self.get_conn()

    def get_conn(self):
        this = self

        class _Conn(ConnWithWS):
            async def receive(self):
                return await this.receiver()

        return _Conn


@pytest.fixture
def adapter():
    return TestAdapter


@pytest.fixture
def app(adapter):
    async def simple_plug(conn):
        await conn.send_resp(b"hello", status=200, halt=True)
        return conn

    return adapter(simple_plug)


@pytest.fixture
def echo_plug():
    async def echo_plug(conn):
        body = await conn.body()
        await conn.send_resp(body, halt=True)
        return conn

    return echo_plug


@pytest.fixture
def echo_app(adapter, echo_plug):
    return adapter(echo_plug)
