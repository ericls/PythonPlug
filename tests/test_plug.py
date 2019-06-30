from PythonPlug.plug import Plug


def test_plug_plugs(adapter, echo_plug):
    async def foo(conn):
        if conn.scope.get("path") == "/foo":
            await conn.send_resp(b"foo", halt=True)
        return conn

    class MyPlug(Plug):
        plugs = [foo]

        async def call(self, conn):
            await conn.send_resp(b"bar", halt=True)

    app = adapter(MyPlug())
    res = app.test_client.get("/foo")
    assert res.content == b"foo"
    res = app.test_client.get("/")
    assert res.content == b"bar"
