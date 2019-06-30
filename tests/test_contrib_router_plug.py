from PythonPlug.contrib.plug.router_plug import RouterPlug
from PythonPlug.plug import Plug


def test_router_plug(adapter):

    my_router = RouterPlug()

    @my_router.route("/foo/<name>/")
    async def foo_name(conn):
        await conn.send_resp(
            f"hello {conn.router_args['name']}".encode("utf-8"), halt=True
        )

    @my_router.route("/echo", methods=["POST"])
    async def plug(conn):
        body = await conn.body()
        await conn.send_resp(body, halt=True)
        return conn

    @my_router.route("/echo", methods=["GET"])
    async def plug_get(conn):
        await conn.send_resp(b"1", halt=True)
        return conn

    @my_router.route("/test/", methods=["GET"])
    async def test(conn):
        await conn.send_resp(b"1", halt=True)
        return conn

    @my_router.route("/add/<int:num1>/<int:num2>", methods=["GET"])
    async def add(conn):
        num1 = conn.router_args["num1"]
        num2 = conn.router_args["num2"]
        await conn.send_resp(f"{num1 + num2}".encode(), halt=True)
        return conn

    class SomePlug(Plug):
        async def call(self, conn):
            await conn.send_resp(b"some plug", halt=True)
            return conn

    my_router.add_route(rule_string="/some_plug", plug=SomePlug(), methods=["GET"])

    class MyPlug(Plug):
        plugs = [my_router]

        async def call(self, conn):
            await conn.send_resp(b"fallback", halt=True)
            return conn

    app = adapter(MyPlug())
    res = app.test_client.get("/echo")
    assert res.content == b"1"
    res = app.test_client.post("/echo", data=b"111")
    assert res.content == b"111"
    res = app.test_client.put("/echo", data=b"111")
    assert res.status_code == 405
    res = app.test_client.get("/test", allow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"].endswith("/test/")
    res = app.test_client.get("/fjdksl", allow_redirects=False)
    assert res.content == b"fallback"
    res = app.test_client.get("/add/1/2", allow_redirects=False)
    assert res.content == b"3"
    res = app.test_client.get("/some_plug")
    assert res.content == b"some plug"


def test_sub_route(adapter):
    my_router = RouterPlug()

    sub_route = RouterPlug()
    sub_route2 = RouterPlug()

    @sub_route.route("/1")
    async def sub_1(conn):
        return await conn.send_resp(b"1", halt=True)

    @sub_route.route("/2")
    async def sub_2(conn):
        return await conn.send_resp(b"2", halt=True)

    @sub_route2.route("/1")
    async def sub_1(conn):
        return await conn.send_resp(b"nested 1", halt=True)

    sub_route.forward(prefix="/nested", router=sub_route2)

    my_router.forward(prefix="/sub", router=sub_route)

    app = adapter(my_router)
    res = app.test_client.get("/sub/1")
    assert res.content == b"1"
    res = app.test_client.get("/sub/2")
    assert res.content == b"2"
    res = app.test_client.get("/sub/nested/1")
    assert res.content == b"nested 1"


def test_sub_route_forwarding_change_path(adapter):
    my_router = RouterPlug()

    sub_route = RouterPlug()
    sub_route2 = RouterPlug()

    sub_route.forward(prefix="/nested", router=sub_route2)

    my_router.forward(prefix="/sub", router=sub_route)

    async def sub_router2_foo(conn):
        return await conn.send_resp(conn.scope["path"].encode(), halt=True)

    sub_route2.forward(prefix="/foo", router=sub_router2_foo, change_path=True)

    app = adapter(my_router)
    assert app.test_client.get("/sub/nested/foo/bar").content == b"/bar"
