import asyncio

from app.hub import Conn, Hub
from app.turn import TurnIO


class FakeWS:
    def __init__(self): self.sent = []
    async def send_json(self, m): self.sent.append(m)
    async def send_bytes(self, b): pass


def make_io(devices):
    hub, conns = Hub(), {}
    for d in devices:
        c = Conn(FakeWS(), "u1", d, d); hub.add(c); conns[d] = c
    io = object.__new__(TurnIO)
    io.hub, io.origin, io.user = hub, conns[devices[-1]], type("U", (), {"id": "u1"})()
    return io, hub, conns


async def ask(io, hub, skill, args, answer=None):
    task = asyncio.create_task(io.request_action(skill, args, "chat"))
    for _ in range(50):
        await asyncio.sleep(0.01)
        if hub.pending or task.done():
            break
    if hub.pending and answer is not None:
        list(hub.pending.values())[0][1].set_result(answer)
    return await asyncio.wait_for(task, 3)


def test_a_phone_alone_can_still_set_reminders_open_pages_and_search():
    for skill, args in (("set_reminder", {"minutes": 5, "message": "tea"}), ("open_url", {"url": "https://example.com"}), ("search_web", {"query": "pizza"})):
        io, hub, conns = make_io(["mobile"])
        res = asyncio.run(ask(io, hub, skill, args, {"ok": True, "output": "done"}))
        assert res["ok"] and [m["skill"] for m in conns["mobile"].ws.sent if m["type"] == "action_request"] == [skill]


def test_a_phone_alone_cannot_touch_the_computer():
    io, hub, conns = make_io(["mobile"])
    res = asyncio.run(ask(io, hub, "run_shell", {"command": "dir"}))
    assert not res["ok"] and "desktop" in res["error"].lower() and not conns["mobile"].ws.sent


def test_computer_actions_still_go_to_the_desktop_when_it_is_online():
    io, hub, conns = make_io(["desktop", "mobile"])                     # the phone is the origin of the request
    res = asyncio.run(ask(io, hub, "open_app", {"app": "notepad"}, {"ok": True}))
    assert res["ok"] and conns["desktop"].ws.sent and not conns["mobile"].ws.sent
    io, hub, conns = make_io(["desktop", "mobile"])
    asyncio.run(ask(io, hub, "set_reminder", {"minutes": 5, "message": "x"}, {"ok": True}))
    assert conns["desktop"].ws.sent                                       # with a desktop online, even reminders live there as before
