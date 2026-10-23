# SikLemau: Township Health Agent

**Sik lemau, sik mau lemau.** SikLemau is Sarawakian Malay for "not weak".

Entry for the Sime Darby Property University Hackathon 2026 (People track), Team Alpha-5.
**Project Pitch Deck (PDF):** [View Pitch Deck](./docs/SikLemau-PitchDeck.pdf)


## What it is
An AI health agent that uses the township itself as the health system. It checks on residents, escalates when something is wrong, supports everyday habits (Eat, Move, Mind), connects neighbours through shared health goals, and gives the township team anonymised insights.

## Try it
- **Visual demo (no install):** https://fatinshadi.github.io/siklemau-prototype/ (synthetic data, scripted examples)
- **Live Telegram bot:** `bot/siklemau_bot.py`. See `bot/README_BOT.md` to run it with your own bot token. With one Telegram account, send `/demo` and that account plays every role.

## Where things stand

**Built and tested with test accounts**
- **Check-in Circle:** daily check-in, then reminder, neighbour volunteer, guardhouse and family if there is no reply. The ladder is deterministic code, not AI. Neighbour buttons ("On my way", "Can't right now"), an all-clear to everyone alerted, and a consent-based circle joined by code and revocable with `/revoke`.
- **Daily Wellbeing (Eat, Move, Mind):** tap requests or type anything. Replies use a Gemini key if provided, with built-in replies as a fallback. It does not diagnose. Red-flag words trigger 999 advice and alert the neighbour.
- **Neighbour groups, issue reports and air quality:** `/groups`, `/report` (sent to a linked township management account) and `/air` (Open-Meteo).
- **Township Insights:** `/insights` shows anonymised totals and average check-in response by block, with recommendations for slow blocks. `/seed` adds synthetic demo data.
- **Tests:** `bot/test_bot.py` covers the escalation ladder, all-clear, neighbour responses, red flags, revoke, groups, reports and insights.

**Not built yet**
- WhatsApp or township app channel, production hosting, and a graphical dashboard (the web page is a visual demo with synthetic data).
- Real clinic booking, voice notes, multi-language replies tuned for BM, Mandarin and Tamil, and a PDPA-reviewed production data design.
- Group matching by schedule and language (the groups are a fixed demo list).

## Repository layout
```
index.html        visual demo (GitHub Pages)
bot/              Telegram bot, tests and setup guide
docs/             pitch deck
```

## Safety and privacy
No diagnosis. Red flags go to 999 advice. Every contact in a circle is opt-in and revocable. Designed for PDPA, with anonymised aggregation for insights. This prototype uses test accounts and synthetic data only. The bot token and Gemini key are read from environment variables and never stored in the repo.

## Team
Alpha-5 from UNIMAS: 
1. Fatin Shadi
2. Melanie Bernard
3. Charmaine Toh
4. Shaneryn Samson
5. Jawa Denis
