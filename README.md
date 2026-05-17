# AI Candidate Phone Screener

An AI-powered outbound phone screening agent built on LiveKit. It calls candidates, conducts a structured screening conversation, and saves a classified result (qualified / maybe / rejected) as JSON and CSV — no human recruiter needed for the first pass.

---

## How It Works

1. Dispatch a call via `make_call.py` with the candidate's name, phone number, and role.
2. The agent picks up the job, dials the candidate over SIP, and speaks first.
3. Aria (the AI recruiter) conducts a natural 5-question screening conversation.
4. After the goodbye, the agent silently classifies the candidate and saves the result to `results/`.
5. `results/all_results.csv` is automatically updated after every call.

---

## Stack

| Layer | Technology |
|---|---|
| Agent framework | LiveKit Agents |
| STT | Deepgram Nova 3 (multilingual) |
| LLM | OpenAI GPT-4o Mini |
| TTS | OpenAI TTS or Cartesia Sonic |
| SIP / telephony | Vobiz SIP Trunk via LiveKit |
| Noise cancellation | LiveKit BVC Telephony |

---

## Project Structure

```
candidate-screener/
├── screener/
│   ├── __init__.py
│   ├── criteria.py       # Role configs (ROLE_CRITERIA) and classify()
│   └── export.py         # export_csv() logic + CLI
├── results/              # Auto-created. One JSON per call + all_results.csv
├── agent.py              # Agent entry point  →  python agent.py dev
├── make_call.py          # Dispatch a call   →  python make_call.py ...
├── setup_trunk.py        # One-time SIP setup →  python setup_trunk.py
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Setup

### 1. Clone and create a virtual environment

```powershell
git clone https://github.com/your-org/candidate-screener.git
cd candidate-screener
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
copy .env.example .env
```

Open `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `LIVEKIT_URL` | [cloud.livekit.io](https://cloud.livekit.io) → Project Settings |
| `LIVEKIT_API_KEY` | Same as above |
| `LIVEKIT_API_SECRET` | Same as above |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) |
| `VOBIZ_SIP_DOMAIN` | Vobiz Console → SIP Settings |
| `VOBIZ_USERNAME` | Vobiz Console |
| `VOBIZ_PASSWORD` | Vobiz Console |
| `VOBIZ_OUTBOUND_NUMBER` | Your DID from Vobiz (e.g. `+91XXXXXXXXXX`) |
| `OUTBOUND_TRUNK_ID` | Auto-set by `setup_trunk.py` (see next step) |

### 4. Register the SIP trunk (one-time)

```powershell
python setup_trunk.py
```

Copy the printed `OUTBOUND_TRUNK_ID` into your `.env`. To verify anytime:

```powershell
python setup_trunk.py --list
```

---

## Running a Screening Call

**Terminal 1 — start the agent:**

```powershell
python agent.py dev
```

**Terminal 2 — dispatch a call:**

```powershell
python make_call.py --to +91XXXXXXXXXX --name "Rahul Sharma" --role "Backend Engineer"
```

The agent dials the candidate, conducts the screening, and writes the result to `results/` automatically.

---

## Screening Criteria

Defined in `screener/criteria.py`. Currently configured:

| Role | Required Skills (any one) | Max Notice | CTC Range |
|---|---|---|---|
| Backend Engineer | Python, FastAPI, Django, Go, Node.js | 60 days | 10–25 LPA |
| Frontend Engineer | React, Vue, TypeScript | 45 days | 8–20 LPA |

To add a new role, add an entry to `ROLE_CRITERIA` in `screener/criteria.py`:

```python
"Data Engineer": {
    "required_skills": ["Spark", "Airflow", "dbt", "Python"],
    "max_notice_period_days": 60,
    "ctc_range_lpa": (12, 30),
    "open_to_remote": True,
},
```

---

## Results

Every completed call writes two things to `results/`:

- `{timestamp}_{phone}.json` — full structured record for that candidate
- `all_results.csv` — auto-regenerated after every call, contains all records

**Sample JSON:**

```json
{
  "timestamp": "2026-05-18T14:32:00",
  "candidate_name": "Rahul Sharma",
  "phone_number": "+91XXXXXXXXXX",
  "role": "Backend Engineer",
  "call_outcome": "completed",
  "answers": {
    "current_role": "Software Engineer at TCS",
    "years_experience": "3 years",
    "skills": ["Python", "Django", "PostgreSQL"],
    "notice_period_days": 30,
    "current_ctc_lpa": 14.0,
    "expected_ctc_lpa": 18.0,
    "open_to_relocation": true
  },
  "classification": "qualified",
  "classification_reason": "Skill match: Python. Notice 30d ≤ 60d limit. Expected CTC 18 LPA within range 10-25.",
  "criteria_used": {
    "required_skills": ["Python", "FastAPI", "Django", "Go", "Node.js"],
    "max_notice_period_days": 60,
    "ctc_range_lpa": [10, 25]
  }
}
```

**Classification logic:**

| Result | Condition |
|---|---|
| `qualified` | Skill match + notice OK + CTC in range |
| `maybe` | Skill match + either notice OK or CTC in range |
| `rejected` | No skill match, or both notice and CTC out of range |

**Call outcomes:** `completed`, `not_available`, `declined`, `voicemail`

---

## Exporting to CSV

`results/all_results.csv` is kept up to date automatically. For a filtered export between two dates:

```powershell
# All records
python -m screener.export

# From a specific date onwards
python -m screener.export --from 2026-05-18

# Between two dates
python -m screener.export --from 2026-05-01 --to 2026-05-18

# Custom output path
python -m screener.export --from 2026-05-01 --to 2026-05-18 --out reports/may_batch.csv
```

Filtered exports are saved as `results/export_{from}_to_{to}.csv` so they don't overwrite `all_results.csv`.

---

## TTS Provider

Defaults to OpenAI TTS. To switch to Cartesia, set in `.env`:

```env
TTS_PROVIDER=cartesia
CARTESIA_API_KEY=...
```
