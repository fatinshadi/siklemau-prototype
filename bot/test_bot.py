import time
from siklemau_bot import Bot, Store


class FakeTG:
    def __init__(s): s.sent = []
    def __call__(s, method, params):
        if method == "sendMessage":
            s.sent.append((params["chat_id"], params["text"], params.get("reply_markup")))
        return {}
    def to(s, chat): return [t for c, t, _ in s.sent if c == chat]


def msg(chat, text, name="X"): return {"message": {"text": text, "chat": {"id": chat}, "from": {"first_name": name}}}
def cb(uid, data): return {"callback_query": {"id": "1", "data": data, "from": {"id": uid}}}


def setup(daily="", start=0.0):
    clock = [start]
    tg = FakeTG()
    b = Bot(tg, Store(":memory:"), speed=1, now=lambda: clock[0], daily=daily)
    b.handle(msg(1, "/register Pak Cik Ahmad", "Ahmad"))
    code = b.st.resident(1)[1]
    b.handle(msg(2, f"/neighbour {code}", "Lina"))
    b.handle(msg(3, f"/guard {code}", "Guard"))
    b.handle(msg(4, f"/family {code}", "Siti"))
    tg.sent.clear()
    return b, tg, clock


def at(b, clock, t): clock[0] = t; b.tick()


# A: missed check-in escalates in order
b, tg, c = setup(); b.handle(msg(1, "/checkin")); assert "okay" in tg.to(1)[0]
at(b, c, 4);  assert not tg.to(2)
at(b, c, 6);  assert any("reminder" in t.lower() for t in tg.to(1))
at(b, c, 21); assert any("knock" in t for t in tg.to(2)) and not tg.to(3)
at(b, c, 36); assert any("Welfare check" in t for t in tg.to(3)) and not tg.to(4)
at(b, c, 41); fam = tg.to(4); assert fam and "neighbour Lina alerted" in fam[0] and "guardhouse alerted" in fam[0]
b.handle(cb(1, "ok:1")); c[0] = 42
assert any("confirmed they are okay" in t for t in tg.to(2)) and any("confirmed" in t for t in tg.to(3)) and any("confirmed" in t for t in tg.to(4))
assert "Escalations: neighbour 1, guardhouse 1, family 1" in b.insights()
print("A ok: full escalation ladder and all-clear")

# B: replying in time stops escalation
b, tg, c = setup(); b.handle(msg(1, "/checkin")); c[0] = 3; b.handle(cb(1, "ok:1")); at(b, c, 60)
assert not tg.to(2) and not tg.to(3) and not tg.to(4); print("B ok: on-time reply stops everything")

# C: neighbour on my way -> guard not alerted, family told
b, tg, c = setup(); b.handle(msg(1, "/checkin")); at(b, c, 21); b.handle(cb(2, "omw:1")); at(b, c, 60)
assert not tg.to(3) and any("on the way" in t for t in tg.to(4)) and any("on the way" in t for t in tg.to(1)); print("C ok: neighbour on my way")

# D: neighbour can't -> guard immediately
b, tg, c = setup(); b.handle(msg(1, "/checkin")); at(b, c, 21); b.handle(cb(2, "cant:1"))
assert any("could not help" in t for t in tg.to(3)); print("D ok: neighbour can't escalates to guard")

# E: red flag
b, tg, c = setup(); b.handle(msg(1, "I have chest pain"))
assert "999" in tg.to(1)[0] and tg.to(2); print("E ok: red flag -> 999 + neighbour")

# F: wellbeing fallback
b, tg, c = setup(); b.handle(msg(1, "I have RM15 for lunch")); assert "Suku-Suku Separuh" in tg.to(1)[0]
b.handle(msg(1, "I feel stressed")); assert "box breathing" in tg.to(1)[1]; print("F ok: wellbeing replies")

# G: wrong code, wrong user callback, revoke
b, tg, c = setup(); b.handle(msg(9, "/neighbour ZZZZ")); assert "not found" in tg.to(9)[0]
b.handle(msg(1, "/checkin")); at(b, c, 21); b.handle(cb(99, "omw:1")); at(b, c, 36)
assert any("Welfare" in t for t in tg.to(3)); print("G ok: stranger cannot hijack")
b2, tg2, c2 = setup(); b2.handle(msg(1, "/revoke")); b2.handle(msg(1, "/checkin")); at(b2, c2, 60)
assert not tg2.to(2) and not tg2.to(3) and not tg2.to(4); print("H ok: revoke removes contacts")

# I: scheduled daily check-in
t8 = time.mktime(time.strptime("2026-10-24 08:00:00", "%Y-%m-%d %H:%M:%S"))
b, tg, c = setup(daily="08:00", start=t8 - 100); at(b, c, t8); assert any("okay" in t for t in tg.to(1))
n = len(tg.sent); at(b, c, t8 + 1); assert len(tg.sent) == n; print("I ok: daily check-in once per day")
# J: groups, report, block insights
b, tg, c = setup(); b.handle(msg(1, "/groups")); assert len(tg.to(1)) == 5
b.handle(cb(1, "join:0")); assert any("Joined" in t for t in tg.to(1)); assert b.st.group_total() == 1
b.handle(msg(5, "/management " + b.st.resident(1)[1], "Mgmt")); b.handle(msg(1, "/block C"))
b.handle(msg(1, "/report Lake track light broken")); assert any("Lake track light" in t for t in tg.to(5)) and "Block C" in tg.to(5)[-1]
b.handle(msg(1, "/checkin")); at(b, c, 25); b.handle(cb(1, "ok:1"))
b.handle(msg(1, "/seed")); ins = b.insights(); assert "Block C" in ins and "community programme" in ins and "synthetic" in ins
print("J ok: groups, report, block insights")
# K: wellbeing buttons
b, tg, c = setup(); b.handle(msg(1, "/wellbeing")); assert tg.sent[-1][2] and len(tg.sent[-1][2]["inline_keyboard"]) == 3
b.handle(cb(1, "wb:0")); assert any("Suku-Suku Separuh" in t for t in tg.to(1))
b.handle(cb(1, "wb:1")); assert any("15-minute walk" in t for t in tg.to(1))
b.handle(cb(1, "wb:2")); assert any("box breathing" in t for t in tg.to(1))
print("K ok: Eat, Move, Mind buttons")
# L: solo demo, one account plays every role
clock = [0.0]; tg = FakeTG(); b = Bot(tg, Store(":memory:"), speed=1, now=lambda: clock[0])
b.handle(msg(1, "/demo")); tg.sent.clear(); b.handle(msg(1, "/checkin"))
for t_ in (6, 21, 36, 41): at(b, clock, t_)
allm = " ".join(tg.to(1))
assert "[NEIGHBOUR VOLUNTEER]" in allm and "[GUARDHOUSE]" in allm and "[FAMILY CONTACT]" in allm and "reminder" in allm.lower()
b.handle(cb(1, "ok:1")); assert sum("confirmed they are okay" in t for t in tg.to(1)) == 3
b.handle(msg(1, "/checkin")); at(b, clock, 70); at(b, clock, 92); b.handle(cb(1, "omw:1")); assert any("on the way" in t for t in tg.to(1))
b.handle(msg(1, "/report broken light")); assert any("[TOWNSHIP MANAGEMENT]" in t for t in tg.to(1))
print("L ok: solo demo with one account")
print("ALL TESTS PASSED")
