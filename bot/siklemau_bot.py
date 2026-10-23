"""SikLemau: township health agent as a Telegram bot.
Standard library only. Run:  python siklemau_bot.py
Env: BOT_TOKEN (required), GEMINI_API_KEY (optional), SECONDS_PER_MINUTE (60 = real time, 1 = demo),
     DAILY_CHECKIN (optional, e.g. 08:00, local time)
"""
import os, json, time, random, sqlite3, threading, socket, urllib.request

# Force IPv4: on some Windows networks IPv6 connections to Telegram hang ~21s before falling back.
if os.environ.get("FORCE_IPV4", "1") == "1":
    _orig_getaddrinfo = socket.getaddrinfo
    socket.getaddrinfo = lambda host, port, family=0, type=0, proto=0, flags=0: _orig_getaddrinfo(
        host, port, socket.AF_INET, type, proto, flags)

STEPS = [(5, "reminder"), (20, "neighbour"), (35, "guard"), (40, "family")]  # minutes after check-in
RED_FLAGS = ["chest pain", "can't breathe", "cannot breathe", "sesak nafas", "sakit dada", "pengsan",
             "faint", "stroke", "bleeding", "berdarah", "suicide", "bunuh diri", "kill myself"]
ROLE_LABEL = {"neighbour": "neighbour volunteer", "guard": "guardhouse", "family": "family contact",
              "management": "township management"}
GROUPS = [("Aisyah & 3 others", "Morning walk, Lake Track, 7:00", "BM / English"),
          ("Uncle Tan's badminton group", "Community hall, Sat 8:00", "Mandarin / English"),
          ("Caregiver circle", "Online + monthly meetup", "BM / Tamil / English"),
          ("Kavitha (walking buddy)", "Park loop, 6:30 pm", "Tamil / English")]
WB_PROMPTS = ["I have RM15 for lunch. What can I eat?", "I have 15 minutes and no equipment. Suggest a short walk or workout.",
              "I feel stressed and only have 5 minutes."]
SYNTH = {"A": 6, "B": 9, "C": 27, "D": 8, "E": 12, "F": 7, "G": 19, "H": 10}  # synthetic demo data (minutes)

HELP = ("🌿 SikLemau: sik lemau, sik mau lemau.\n\n"
        "I check in on residents, alert the people they trust if there is no reply, and help with Eat, Move and Mind.\n\n"
        "Resident: /register [name], /block C, /checkin (test now), /status, /revoke\n"
        "Eat, Move, Mind: /wellbeing (tap a request) or just type to me\n"
        "Resident actions: /groups (join walking and caregiver groups), /report <issue>, /air\n"
        "Circle members: /neighbour CODE, /guard CODE, /family CODE, /management CODE\n"
        "Anyone: /insights (anonymised stats), /seed (add synthetic demo data)\n"
        "Solo demo with one account: /demo (you play every role)\n\n"
        "Registered residents can message me anything about food, exercise or stress. "
        "I do not diagnose. In an emergency call 999.")

SYSTEM = ("You are SikLemau, a friendly township health assistant for Malaysian residents. Reply briefly (max 90 words) "
          "with practical help on food, light exercise and stress relief. Use the Malaysian Healthy Plate (Suku-Suku Separuh: "
          "half vegetables and fruit, a quarter carbohydrate, a quarter protein) and local foods. Never diagnose or advise on "
          "medication. Label nutrition numbers as estimates. If the user describes symptoms or distress, tell them to see a doctor "
          "or call 999 if urgent. Reply in the user's language (BM, English, Mandarin or Tamil).")


class Store:
    def __init__(s, path="siklemau.db"):
        s.db = sqlite3.connect(path)
        s.db.executescript("""
        CREATE TABLE IF NOT EXISTS residents(chat_id INTEGER PRIMARY KEY, name TEXT, code TEXT);
        CREATE TABLE IF NOT EXISTS links(resident INTEGER, role TEXT, chat_id INTEGER, name TEXT, PRIMARY KEY(resident, role));
        CREATE TABLE IF NOT EXISTS events(ts REAL, resident INTEGER, kind TEXT, val REAL);
        CREATE TABLE IF NOT EXISTS group_members(idx INTEGER, chat_id INTEGER, PRIMARY KEY(idx, chat_id));""")
        try:
            s.db.execute("ALTER TABLE residents ADD COLUMN block TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

    def resident(s, chat):
        return s.db.execute("SELECT name, code FROM residents WHERE chat_id=?", (chat,)).fetchone()

    def all_residents(s):
        return [r[0] for r in s.db.execute("SELECT chat_id FROM residents")]

    def add_resident(s, chat, name):
        row = s.resident(chat)
        code = row[1] if row else "".join(random.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(4))
        s.db.execute("INSERT INTO residents(chat_id, name, code) VALUES(?,?,?) ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name", (chat, name, code))
        s.db.commit()
        return code

    def by_code(s, code):
        return s.db.execute("SELECT chat_id, name FROM residents WHERE code=?", (code,)).fetchone()

    def link(s, rid, role, chat, name):
        s.db.execute("INSERT OR REPLACE INTO links VALUES(?,?,?,?)", (rid, role, chat, name))
        s.db.commit()

    def get_link(s, rid, role):
        return s.db.execute("SELECT chat_id, name FROM links WHERE resident=? AND role=?", (rid, role)).fetchone()

    def links(s, rid):
        return s.db.execute("SELECT role, name FROM links WHERE resident=?", (rid,)).fetchall()

    def revoke(s, rid):
        s.db.execute("DELETE FROM links WHERE resident=?", (rid,))
        s.db.commit()

    def event(s, rid, kind, val=0.0, ts=None):
        s.db.execute("INSERT INTO events VALUES(?,?,?,?)", (ts or time.time(), rid, kind, val))
        s.db.commit()

    def set_block(s, chat, block):
        s.db.execute("UPDATE residents SET block=? WHERE chat_id=?", (block.upper(), chat))
        s.db.commit()

    def block_of(s, chat):
        r = s.db.execute("SELECT block FROM residents WHERE chat_id=?", (chat,)).fetchone()
        return r[0] if r and r[0] else None

    def block_stats(s):
        rows = s.db.execute("SELECT r.block, AVG(e.val) FROM events e JOIN residents r ON r.chat_id=e.resident "
                            "WHERE e.kind='checkin_ok' AND r.block IS NOT NULL GROUP BY r.block").fetchall()
        return {b: v for b, v in rows}

    def join_group(s, idx, chat):
        s.db.execute("INSERT OR IGNORE INTO group_members VALUES(?,?)", (idx, chat))
        s.db.commit()
        return s.db.execute("SELECT COUNT(*) FROM group_members WHERE idx=?", (idx,)).fetchone()[0]

    def group_total(s):
        return s.db.execute("SELECT COUNT(*) FROM group_members").fetchone()[0]

    def count(s, kind):
        return s.db.execute("SELECT COUNT(*) FROM events WHERE kind=?", (kind,)).fetchone()[0]

    def avg(s, kind):
        v = s.db.execute("SELECT AVG(val) FROM events WHERE kind=?", (kind,)).fetchone()[0]
        return v or 0.0


def make_tg(token):
    def tg(method, params):
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                     data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=40) as r:
            res = json.load(r)
        dt = time.time() - t0
        if dt > 1 and method != "getUpdates":
            print(f"[slow] Telegram {method} took {dt:.1f}s (network)")
        if not res.get("ok"):
            raise RuntimeError(res)
        return res["result"]
    return tg


class Bot:
    def __init__(s, tg, store, speed=60.0, now=time.time, gemini_key="", daily=""):
        s.tg, s.st, s.speed, s.now = tg, store, speed, now
        s.key, s.daily, s.last_daily = gemini_key, daily, ""
        s.pending, s.offset, s.seed = {}, 0, False

    # ---------- helpers ----------
    def send(s, chat, text, buttons=None):
        params = {"chat_id": chat, "text": text}
        if buttons:
            rows = buttons if isinstance(buttons[0], list) else [buttons]
            params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}
        try:
            s.tg("sendMessage", params)
        except Exception as e:
            print("send failed:", chat, e)

    def send_role(s, rid, chat, role, text, buttons=None):
        """Send to a circle member. In solo demo (member chat == resident chat) label who is receiving."""
        if chat == rid:
            text = f"[{ROLE_LABEL[role].upper()}] " + text
        s.send(chat, text, buttons)

    def name(s, rid):
        r = s.st.resident(rid)
        return r[0] if r else "Resident"

    # ---------- updates ----------
    def handle(s, u):
        if "callback_query" in u:
            return s.on_callback(u["callback_query"])
        m = u.get("message") or {}
        text, chat = (m.get("text") or "").strip(), m.get("chat", {}).get("id")
        who = m.get("from", {}).get("first_name", "Friend")
        if not text or chat is None:
            return
        if text.startswith("/"):
            return s.command(chat, who, text)
        if s.st.resident(chat):
            return s.wellbeing(chat, text)
        s.send(chat, "Hi! Send /start to see how SikLemau works, or /register to set up a resident profile.")

    def command(s, chat, who, text):
        parts = text.split()
        cmd, arg = parts[0].split("@")[0].lower(), (parts[1] if len(parts) > 1 else "")
        if cmd in ("/start", "/help"):
            s.send(chat, HELP)
        elif cmd == "/register":
            rname = " ".join(parts[1:]) or who
            code = s.st.add_resident(chat, rname)
            s.send(chat, f"Registered {rname}. Your circle code: {code}\n\nShare it only with people you trust. They join by sending:\n"
                         f"/neighbour {code}\n/guard {code}\n/family {code}\n\nRemove everyone any time with /revoke.")
        elif cmd in ("/neighbour", "/guard", "/family", "/management"):
            r = s.st.by_code(arg.upper())
            if not r:
                return s.send(chat, "Code not found. Ask the resident for their circle code.")
            rid, rname = r
            role = cmd[1:]
            s.st.link(rid, role, chat, who)
            s.send(chat, f"You are now {rname}'s {ROLE_LABEL[role]}. Thank you for looking out for them.")
            s.send(rid, f"✅ {who} joined your circle as {ROLE_LABEL[role]}.")
        elif cmd == "/checkin":
            if s.st.resident(chat):
                s.start_checkin(chat)
            else:
                s.send(chat, "Only registered residents can check in. Send /register first.")
        elif cmd == "/status":
            if not s.st.resident(chat):
                return s.send(chat, "Send /register first.")
            ls = s.st.links(chat)
            s.send(chat, "Your circle:\n" + ("\n".join(f"- {ROLE_LABEL[r]}: {n}" for r, n in ls) if ls else "No one linked yet."))
        elif cmd == "/revoke":
            if s.st.resident(chat):
                s.st.revoke(chat)
                s.send(chat, "All contacts removed. They will no longer be alerted.")
        elif cmd == "/insights":
            s.send(chat, s.insights())
        elif cmd == "/demo":
            s.st.add_resident(chat, "Pak Cik Ahmad")
            s.st.set_block(chat, "C")
            for role, nm in [("neighbour", "Puan Lina"), ("guard", "Guardhouse"), ("family", "Siti"),
                             ("management", "Township management")]:
                s.st.link(chat, role, chat, nm)
            s.send(chat, "Solo demo ready. This chat plays every role: resident Pak Cik Ahmad (Block C), neighbour Puan Lina, "
                         "guardhouse, family (Siti) and township management. Alerts are labelled like [NEIGHBOUR VOLUNTEER]. "
                         "Send /checkin and do not tap the button. Then try /wellbeing, /groups, /report <issue>, /seed and /insights.")
        elif cmd == "/block":
            if s.st.resident(chat) and arg:
                s.st.set_block(chat, arg)
                s.send(chat, f"Block set to {arg.upper()}.")
            else:
                s.send(chat, "Register first, then send e.g. /block C")
        elif cmd == "/seed":
            s.seed = not s.seed
            s.send(chat, "Synthetic demo data " + ("ON: /insights now includes synthetic blocks." if s.seed else "OFF."))
        elif cmd in ("/wellbeing", "/menu"):
            if not s.st.resident(chat):
                return s.send(chat, "Send /register first.")
            s.send(chat, "Eat, Move, Mind. Tap a request, or type your own:",
                   [[("🍚 Eat: I have RM15 for lunch", "wb:0")], [("🚶 Move: 15 minutes, no equipment", "wb:1")],
                    [("😮\u200d💨 Mind: I feel stressed, 5 minutes", "wb:2")]])
        elif cmd == "/groups":
            s.send(chat, "Neighbour groups (opt-in). Tap Join:")
            for i, (title, when, lang) in enumerate(GROUPS):
                s.send(chat, f"{title}\n{when} | {lang}", [("Join", f"join:{i}")])
        elif cmd == "/report":
            s.report(chat, " ".join(parts[1:]))
        elif cmd == "/air":
            s.send(chat, s.air())
        else:
            s.send(chat, "Unknown command. Send /help.")

    # ---------- check-in and escalation ----------
    def start_checkin(s, rid):
        if rid in s.pending:
            return
        s.pending[rid] = {"t0": s.now(), "done": set(), "notified": set(), "log": ["0 min: check-in sent"], "nb": None}
        s.st.event(rid, "checkin_sent", ts=s.now())
        s.send(rid, "Selamat pagi! Tap ✅ if you are okay today.", [("✅ I'm okay", f"ok:{rid}")])

    def tick(s):
        if s.daily:
            lt = time.localtime(s.now())
            day = time.strftime("%Y-%m-%d", lt)
            if time.strftime("%H:%M", lt) == s.daily and s.last_daily != day:
                s.last_daily = day
                for rid in s.st.all_residents():
                    s.start_checkin(rid)
        for rid, p in list(s.pending.items()):
            mins = (s.now() - p["t0"]) / s.speed
            for m, stage in STEPS:
                if mins >= m and stage not in p["done"]:
                    p["done"].add(stage)
                    s.escalate(rid, stage, p, m)
            if mins > 180:
                s.pending.pop(rid, None)

    def escalate(s, rid, stage, p, m):
        rname = s.name(rid)
        if stage == "reminder":
            s.send(rid, "No reply yet. Gentle reminder: are you okay?", [("✅ I'm okay", f"ok:{rid}")])
            p["log"].append(f"{m} min: reminder sent")
            return
        link = s.st.get_link(rid, stage)
        if not link:
            return
        chat, who = link
        if stage == "neighbour":
            s.send_role(rid, chat, "neighbour", f"{rname} has not checked in this morning. Could you knock on their door?",
                   [("🚶 On my way", f"omw:{rid}"), ("Can't right now", f"cant:{rid}")])
            p["log"].append(f"{m} min: neighbour {who} alerted")
        elif stage == "guard":
            why = "The neighbour volunteer could not help." if p["nb"] == "cant" else "There was no response to reminders or the neighbour alert."
            s.send_role(rid, chat, "guard", f"🛡 Welfare check needed: {rname} missed the daily check-in. {why} Please check on them.",
                   [("Acknowledged", f"ack:{rid}")])
            p["log"].append(f"{m} min: guardhouse alerted")
        elif stage == "family":
            s.send_role(rid, chat, "family", f"⚠️ {rname} missed the daily check-in. What we have done:\n- " + "\n- ".join(p["log"]) +
                         "\nPlease contact them if you can.")
        p["notified"].add(stage)
        s.st.event(rid, "esc_" + stage, m, ts=s.now())

    def on_callback(s, cb):
        try:
            s.tg("answerCallbackQuery", {"callback_query_id": cb["id"]})
        except Exception:
            pass
        action, _, r = cb.get("data", "").partition(":")
        if not r.lstrip("-").isdigit():
            return
        if action == "wb":
            idx, uid = int(r), cb["from"]["id"]
            if 0 <= idx < len(WB_PROMPTS) and s.st.resident(uid):
                s.send(uid, "You: " + WB_PROMPTS[idx])
                s.wellbeing(uid, WB_PROMPTS[idx])
            return
        if action == "join":
            idx = int(r)
            if 0 <= idx < len(GROUPS):
                n = s.st.join_group(idx, cb["from"]["id"])
                s.st.event(cb["from"]["id"], "group_join", idx, ts=s.now())
                s.send(cb["from"]["id"], f"Joined \u2713 {GROUPS[idx][0]}. Members so far: {n}. You can leave any time.")
            return
        rid, uid = int(r), cb["from"]["id"]
        p = s.pending.get(rid)
        nb = s.st.get_link(rid, "neighbour")
        gd = s.st.get_link(rid, "guard")
        if action == "ok" and uid == rid:
            s.confirm_ok(rid)
        elif action == "omw" and p and nb and uid == nb[0]:
            p["nb"] = "omw"
            p["done"].update({"guard", "family"})
            s.send(rid, f"Your neighbour {nb[1]} is on the way to check on you.")
            fam = s.st.get_link(rid, "family")
            if fam:
                s.send_role(rid, fam[0], "family", f"Update: neighbour {nb[1]} is on the way to check on {s.name(rid)}.")
                p["notified"].add("family")
            p["notified"].add("neighbour")
            s.st.event(rid, "nb_omw", ts=s.now())
        elif action == "cant" and p and nb and uid == nb[0]:
            p["nb"] = "cant"
            s.send_role(rid, nb[0], "neighbour", "Thanks for letting us know. We will alert the guardhouse.")
            if "guard" not in p["done"]:
                p["done"].add("guard")
                s.escalate(rid, "guard", p, round((s.now() - p["t0"]) / s.speed))
        elif action == "ack" and p and gd and uid == gd[0]:
            s.send_role(rid, gd[0], "guard", "Thank you. Please update the family once you have checked.")
            fam = s.st.get_link(rid, "family")
            if fam:
                s.send_role(rid, fam[0], "family", f"Update: the guardhouse has acknowledged and is checking on {s.name(rid)}.")

    def confirm_ok(s, rid):
        p = s.pending.pop(rid, None)
        if not p:
            return s.send(rid, "Thank you, you are all set. Have a healthy day!")
        mins = (s.now() - p["t0"]) / s.speed
        s.st.event(rid, "checkin_ok", mins, ts=s.now())
        for role in p["notified"]:
            link = s.st.get_link(rid, role)
            if link:
                s.send_role(rid, link[0], role, f"✅ {s.name(rid)} has confirmed they are okay. Thank you.")
        s.send(rid, "Thank you! Have a healthy day. 🌿")

    # ---------- wellbeing ----------
    def wellbeing(s, chat, text):
        s.st.event(chat, "wellbeing", ts=s.now())
        low = text.lower()
        if any(k in low for k in RED_FLAGS):
            s.send(chat, "This could be serious. Please call 999 now or ask someone nearby for help. I am not able to diagnose.")
            nb = s.st.get_link(chat, "neighbour")
            if nb:
                s.send_role(chat, nb[0], "neighbour", f"{s.name(chat)} mentioned a possible urgent health concern. Please check on them if you can.")
            s.st.event(chat, "red_flag", ts=s.now())
            return
        if not s.key:
            return s.send(chat, s.rules(low))
        try:
            s.tg("sendChatAction", {"chat_id": chat, "action": "typing"})
        except Exception:
            pass
        threading.Thread(target=s._ai_reply, args=(chat, text, low), daemon=True).start()

    def _ai_reply(s, chat, text, low):
        t0 = time.time()
        reply = s.llm(text)
        print(f"[ai] Gemini {'answered' if reply else 'failed, used fallback'} in {time.time() - t0:.1f}s")
        s.send(chat, reply or s.rules(low))

    def llm(s, text):
        if not s.key:
            return None
        model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        body = {"system_instruction": {"parts": [{"text": SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": text}]}],
                "generationConfig": {"maxOutputTokens": 300}}
        try:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={s.key}",
                data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print("LLM failed, using fallback:", e)
            return None

    def rules(s, low):
        if any(k in low for k in ["lunch", "dinner", "breakfast", "makan", "eat", "food", "rm"]):
            return ("Try a food-stall plate that follows Suku-Suku Separuh: half vegetables and fruit, a quarter rice, a quarter protein "
                    "such as fish, egg or tofu. Swap sweet drinks for plain water or kurang manis. (Nutrition values are estimates.)")
        if any(k in low for k in ["walk", "jalan", "exercise", "workout", "senam", "equipment", "gym"]):
            return "A brisk 15-minute walk is a good start. Warm up for 2 minutes, walk at a pace where you can still talk, then stretch. Walking with a neighbour is even better."
        if any(k in low for k in ["stress", "tired", "penat", "sad", "overwhelm", "anxious"]):
            return ("Let's try box breathing: in for 4 seconds, hold 4, out 4, hold 4, five rounds. "
                    "If you feel unsafe or very low, please talk to someone you trust or call 999.")
        return "I can help with food, light exercise and stress relief. Try: \"I have RM15 for lunch\", \"I have 15 minutes to exercise\" or \"I feel stressed\"."

    # ---------- actions ----------
    def report(s, chat, text):
        r = s.st.resident(chat)
        if not r:
            return s.send(chat, "Register first with /register.")
        if not text:
            return s.send(chat, "Tell me what to report, e.g. /report Lake track light is broken near bench 3")
        blk = s.st.block_of(chat)
        mg = s.st.get_link(chat, "management")
        s.st.event(chat, "issue", ts=s.now())
        if mg:
            s.send_role(chat, mg[0], "management", f"🛠 Issue reported by {r[0]}" + (f" (Block {blk})" if blk else "") + f":\n{text}")
            s.send(chat, "Reported to township management. Thank you!")
        else:
            s.send(chat, "Saved your report. (Demo: no township management account is linked yet.)")

    def air(s):
        lat, lon = os.environ.get("AIR_LAT", "1.5535"), os.environ.get("AIR_LON", "110.3593")
        try:
            url = (f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
                   "&current=us_aqi,pm2_5")
            with urllib.request.urlopen(url, timeout=8) as r:
                cur = json.load(r)["current"]
            aqi = cur["us_aqi"]
            tip = "Good for a walk." if aqi <= 50 else "Fine for light activity." if aqi <= 100 else "Consider staying indoors."
            return f"Air quality now: US AQI {aqi} (PM2.5 {cur['pm2_5']}). {tip}"
        except Exception:
            return "Could not get air quality right now. Please try again later."

    # ---------- insights ----------
    def insights(s):
        sent, ok = s.st.count("checkin_sent"), s.st.count("checkin_ok")
        blocks = dict(SYNTH) if s.seed else {}
        blocks.update(s.st.block_stats())
        heat = ""
        if blocks:
            lines = []
            for b in sorted(blocks):
                v = blocks[b]
                lines.append(f"{'🟥' if v > 20 else '🟨' if v > 14 else '🟩'} Block {b}: {v:.0f} min")
            slow = [b for b in sorted(blocks) if blocks[b] > 20]
            heat = ("\nAverage check-in response by block" + (" (synthetic demo data)" if s.seed else "") + ":\n" + "\n".join(lines) + "\n")
            if slow:
                heat += "Recommended: " + "; ".join(f"Block {b} has slow responses, start a weekly community programme" for b in slow) + "\n"
        return ("📊 Township Insights (anonymised, aggregated)\n"
                f"Residents registered: {len(s.st.all_residents())}\n"
                f"Check-ins sent: {sent}, confirmed: {ok}\n"
                f"Average response time: {s.st.avg('checkin_ok'):.1f} min\n"
                f"Escalations: neighbour {s.st.count('esc_neighbour')}, guardhouse {s.st.count('esc_guard')}, family {s.st.count('esc_family')}\n"
                f"Wellbeing chats: {s.st.count('wellbeing')}, red-flag referrals: {s.st.count('red_flag')}\n"
                f"Group joins: {s.st.group_total()}, issues reported: {s.st.count('issue')}" + heat)

    def run(s):
        print("SikLemau bot running. Press Ctrl+C to stop.")
        while True:
            try:
                for u in s.tg("getUpdates", {"offset": s.offset, "timeout": 2}):
                    s.offset = u["update_id"] + 1
                    s.handle(u)
            except Exception as e:
                print("poll error:", e)
                time.sleep(2)
            s.tick()


if __name__ == "__main__":
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN first (see README_BOT.md).")
    Bot(make_tg(token), Store(), speed=float(os.environ.get("SECONDS_PER_MINUTE", "60")),
        gemini_key=os.environ.get("GEMINI_API_KEY", ""), daily=os.environ.get("DAILY_CHECKIN", "")).run()
