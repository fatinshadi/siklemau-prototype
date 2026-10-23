# SikLemau: Township Health Agent (prototype)

**Sik lemau, sik mau lemau.** SikLemau is Sarawak Malay for "not weak".

Entry for the Sime Darby Property University Hackathon 2026 (People track), Team Alpha-5.

## What this is
SikLemau is an AI health agent concept that uses the township itself as the health system. It checks on residents, escalates when something is wrong, supports daily habits (Eat, Move, Mind), connects neighbours through shared health goals, and gives the township team anonymised insights.

## What this repository contains
`index.html` is a **front-end prototype**. It simulates the user journey with scripted examples and **synthetic data**:

- **Check-in Circle:** a daily check-in that escalates from reminder to neighbour volunteer, guardhouse and family if there is no reply (time is accelerated in the demo).
- **Neighbours:** an opt-in board of walking and caregiver groups.
- **Daily Wellbeing:** three sample requests and replies (Eat, Move, Mind). These are examples only. The real agent is designed to accept any request.
- **Township Insights:** an anonymised, block-level dashboard with recommended actions (synthetic data).

## What is not built yet
The live Telegram bot, the AI agent with tool calling, the scheduler and the database are **planned, not built**. The prototype does not call any AI model and stores no personal data.

## Planned architecture
Telegram bot (WhatsApp or township app later) -> AI agent with tools (check_in, escalate, find_buddy, report_issue, get_air_quality) -> scheduler and database -> Insights dashboard. Each township is a configuration pack (map, facilities, volunteers).

## Safety and privacy
No diagnosis. Red-flag symptoms are directed to 999 and to a person. Every link to a neighbour or family member is opt-in and revocable. Designed for PDPA, with anonymised aggregation for the dashboard.

## Run it
Open `index.html` in any browser. No installation or internet connection is needed.

## Team
Alpha-5: 
1. Fatin Shadi
2. Melanie Bernard
3. Charmaine Toh
4. Shaneryn Samson
5. Jawa Denis
