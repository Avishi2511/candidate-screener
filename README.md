# AI Candidate Phone Screener

An AI-powered outbound phone screening agent built on LiveKit. It calls candidates, conducts a structured 5-question screening conversation, and saves a classified result (qualified / maybe / rejected) to a JSON file — no human recruiter needed for the first pass.

---

## How It Works

1. You dispatch a call via `make_call.py` with the candidate's name, phone number, and role.
2. The LiveKit agent (`agent.py`) picks up the job, dials the candidate over SIP, and speaks first.
3. The agent (named Aria) conducts a natural screening conversation — current role, skills, notice period, current CTC, expected CTC, relocation preference.
4. After the goodbye, the agent silently calls `submit_screening_result`, which classifies the candidate and writes a JSON file to `screening_results/`.

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
├── agent.py              # Agent logic — screener, tools, criteria, entrypoint
├── make_call.py          # CLI to dispatch a screening call
├── setup_trunk.py        # One-time SIP trunk configuration
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
└── screening_results/    # Auto-created; one JSON file per completed call
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
| `DEFAULT_TRANSFER_NUMBER` | Number to transfer to if candidate requests a human |

### 4. Register the SIP trunk (one-time)

```powershell
python setup_trunk.py
```

This creates or updates the LiveKit SIP trunk with your Vobiz credentials and prints the `OUTBOUND_TRUNK_ID`. Copy it into your `.env`.

To verify the trunk exists:

```powershell
python setup_trunk.py --list
```

---

## Running a Screening Call

### Terminal 1 — Start the agent

```powershell
python agent.py dev
```

The agent connects to LiveKit and waits for a dispatch job. Leave this running.

### Terminal 2 — Dispatch a call

```powershell
python make_call.py --to +91XXXXXXXXXX --name "Rahul Sharma" --role "Backend Engineer"
```

The agent dials the candidate, conducts the screening, and saves the result automatically.

---

## Screening Criteria

Criteria are defined in `ROLE_CRITERIA` at the top of `agent.py`. Currently configured:

| Role | Required Skills (any one) | Max Notice | CTC Range |
|---|---|---|---|
| Backend Engineer | Python, FastAPI, Django, Go, Node.js | 60 days | 10–25 LPA |
| Frontend Engineer | React, Vue, TypeScript | 45 days | 8–20 LPA |

To add a new role, add an entry to `ROLE_CRITERIA` in `agent.py`:

```python
"Data Engineer": {
    "required_skills": ["Spark", "Airflow", "dbt", "Python"],
    "max_notice_period_days": 60,
    "ctc_range_lpa": (12, 30),
    "open_to_remote": True,
},
```

---

## Output

Each call produces a file at `screening_results/{timestamp}_{phone}.json`:

```json
{
  "timestamp": "2026-05-16T14:32:00",
  "phone_number": "+91XXXXXXXXXX",
  "candidate_name": "Rahul Sharma",
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
| `rejected` | Skill mismatch or both notice and CTC out of range |

**Call outcomes:** `completed`, `not_available`, `declined`, `voicemail`

---

## Call Transfer

If the candidate says "I'd rather speak to a human", the agent transfers the call to `DEFAULT_TRANSFER_NUMBER` via SIP REFER. See `transfer_call.md` for detailed troubleshooting.

---

## TTS Provider

The agent defaults to OpenAI TTS. To switch to Cartesia, set in `.env`:

```env
TTS_PROVIDER=cartesia
CARTESIA_API_KEY=...
```
