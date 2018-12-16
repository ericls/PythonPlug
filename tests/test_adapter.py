from PyPlug.adapter import ASGIAdapter


def test_adapter():
    async def plug(conn):
        await conn.send_resp(b"foo", halt=True)

    app = ASGIAdapter(plug)
