from PyPlug.utils.conn import send_json


def test_send_json(adapter):

    async def plug(conn):
        await send_json(conn, {'foo': 'bar'}, status=200, halt=True)

    app = adapter(plug)
    res = app.test_client.get('/')
    assert res.status_code == 200
    assert res.json() == {'foo': 'bar'}
    assert res.headers['content-type'] == 'application/json'
