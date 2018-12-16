from PyPlug.contrib.plug.guard_plug import GuardPlug


def test_guard_plug(adapter):

    guard = GuardPlug()

    @guard.case(lambda conn: conn.scope.get("path") == "/foo")
    async def foo(conn):
        await conn.send_resp(b"foo", halt=True)
        return conn

    app = adapter(guard)
    res = app.test_client.get("/foo")
    assert res.content == b"foo"
