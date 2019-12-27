import logging
import os

from starlette.staticfiles import StaticFiles

from PythonPlug import ASGIAdapter, Conn, Plug, ConnWithWS, ConnType, WSState
from PythonPlug.contrib.plug.router_plug import RouterPlug

from logger_plug import LoggerPlug

my_router = RouterPlug()


async def handle_static(conn: Conn):
    await conn.call_asgi_app(
        StaticFiles(directory=os.path.join(os.path.dirname(__file__), "./static"))
    )


my_router.forward("/static/foo", handle_static, change_path=True)


@my_router.route("/foo/<name>/")
async def foo_name(conn):
    await conn.send_resp(f"hello {conn.router_args['name']}".encode("utf-8"), halt=True)


@my_router.route("/echo")
async def plug(conn):
    body = await conn.body()
    await conn.send_resp(body, halt=True)
    return conn


@my_router.route("/ws")
async def ws_plug(conn: ConnWithWS):
    await conn.ws_accept()
    async for message in conn.iter_messages():
        await conn.send_message(message)
    await conn.ws_close()
    return conn


class Entry(Plug):

    plugs = [LoggerPlug(), my_router]

    async def call(self, conn: ConnWithWS):
        if not conn.started and conn.type == ConnType.http:
            await conn.send_resp(b"1234", halt=True)
        return conn


app = ASGIAdapter(Entry())
