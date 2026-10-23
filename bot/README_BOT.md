# SikLemau Telegram bot: setup and demo

Needs only Python 3.8+ (python.org). No packages to install.

## 1. Create the bot
In Telegram, open **@BotFather**, send `/newbot`, and copy the token. Never post the token or commit it to GitHub.

## 2. (Optional) AI replies
Get a free key at aistudio.google.com. Without it the bot still works using built-in replies. If AI replies fail, set `GEMINI_MODEL` to the current free model name.

## 3. Run
Windows Command Prompts (cmd), in this folder:
```
set BOT_TOKEN=PASTE_TOKEN
set GEMINI_API_KEY=PASTE_KEY
set SECONDS_PER_MINUTE=0.5
python siklemau_bot.py
```
PowerShell: use `$env:BOT_TOKEN="..."`. Mac/Linux: use `export BOT_TOKEN=...`.
`SECONDS_PER_MINUTE=0.5` is demo mode (the 40-minute ladder runs in about 20 seconds). Use `60` for real time. Optional: `DAILY_CHECKIN=08:00` for an automatic daily check-in.

## 4a. Solo demo (one Telegram account)
Send `/demo`. Your account plays every role: resident Pak Cik Ahmad (Block C), neighbour, guardhouse, family and township management. Alerts arrive in the same chat with labels such as [NEIGHBOUR VOLUNTEER]. Then send `/checkin` and do not tap the button.

## 4b. Demo with 4 Telegram accounts
1. Resident: `/register Pak Cik Ahmad`, then `/block C`. The bot returns a 4-character code.
2. Others join with the code: `/neighbour CODE`, `/guard CODE`, `/family CODE`, `/management CODE`.
3. Resident: `/checkin` and do not tap the button. Watch the reminder, neighbour, guard and family alerts. Try "On my way", "Can't right now" and "I'm okay" on other runs.
4. Resident: `/wellbeing` (Eat, Move, Mind buttons), `/groups`, `/report Lake track light is broken`, `/air`.
5. Anyone: `/seed` then `/insights` for block-level insights with synthetic demo data.

## Tests
`python test_bot.py` runs the logic tests (no Telegram needed).

## Notes
Data is stored locally in `siklemau.db`. Use test accounts only. Delete the file to reset.
