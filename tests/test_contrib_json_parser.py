from PythonPlug.contrib.parser.json_parser import parse_json
from PythonPlug.utils.conn import send_json


def test_json_parse(adapter):
    async def plug(conn):
        await parse_json(conn)
        await send_json(conn, conn.json, status=200, halt=True)

    app = adapter(plug)
    res = app.test_client.post("/", json={"foo": "bar"})
    assert res.status_code == 200
    assert res.json() == {"foo": "bar"}


def test_not_json_parse(adapter):
    async def plug(conn):
        await parse_json(conn)
        assert conn.json is None
        await conn.send_resp(b"foo", halt=True)

    app = adapter(plug)
    app.test_client.get("/")
