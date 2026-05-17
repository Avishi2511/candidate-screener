import logging
import os
import json
import datetime
from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai, cartesia, deepgram, noise_cancellation, silero
from livekit.agents import llm
from typing import Annotated

from screener.criteria import ROLE_CRITERIA, DEFAULT_CRITERIA, classify
from screener.export import export_csv, RESULTS_DIR

load_dotenv(".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("candidate-screener")

OUTBOUND_TRUNK_ID = os.getenv("OUTBOUND_TRUNK_ID")


def _build_tts():
    provider = os.getenv("TTS_PROVIDER", "openai").lower()

    if provider == "cartesia":
        logger.info("Using Cartesia TTS")
        model = os.getenv("CARTESIA_TTS_MODEL", "sonic-2")
        voice = os.getenv("CARTESIA_TTS_VOICE", "f786b574-daa5-4673-aa0c-cbe3e8534c02")
        return cartesia.TTS(model=model, voice=voice)

    logger.info("Using OpenAI TTS")
    model = os.getenv("OPENAI_TTS_MODEL", "tts-1")
    voice = os.getenv("OPENAI_TTS_VOICE", "alloy")
    return openai.TTS(model=model, voice=voice)


class ScreeningTools(llm.ToolContext):
    def __init__(self, ctx: agents.JobContext, phone_number: str, candidate_name: str, role: str, criteria: dict):
        super().__init__(tools=[])
        self.ctx = ctx
        self.phone_number = phone_number
        self.candidate_name = candidate_name
        self.role = role
        self.criteria = criteria

    @llm.function_tool(description=(
        "Save the screening result after the call ends. "
        "Call this silently after saying goodbye — the candidate will not hear the result."
    ))
    async def submit_screening_result(
        self,
        current_role: Annotated[str, "Candidate's current job title and company, e.g. 'Software Engineer at TCS'"],
        years_experience: Annotated[str, "Total years of experience, e.g. '3 years'"],
        skills: Annotated[str, "Comma-separated skills as heard, e.g. 'Python, Django, PostgreSQL'"],
        notice_period_days: Annotated[int, "Notice period converted to days, e.g. 2 months = 60"],
        current_ctc_lpa: Annotated[float, "Current CTC in LPA"],
        expected_ctc_lpa: Annotated[float, "Expected CTC in LPA"],
        open_to_relocation: Annotated[bool, "Whether candidate is open to relocation"],
        call_outcome: Annotated[str, "One of: completed, not_available, declined, voicemail"],
    ) -> str:
        skills_list = [s.strip() for s in skills.split(",") if s.strip()]
        classification, reason = classify(skills_list, notice_period_days, expected_ctc_lpa, self.criteria)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
        safe_phone = self.phone_number.replace("+", "").replace(" ", "")

        result = {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "phone_number": self.phone_number,
            "candidate_name": self.candidate_name,
            "role": self.role,
            "call_outcome": call_outcome,
            "answers": {
                "current_role": current_role,
                "years_experience": years_experience,
                "skills": skills_list,
                "notice_period_days": notice_period_days,
                "current_ctc_lpa": current_ctc_lpa,
                "expected_ctc_lpa": expected_ctc_lpa,
                "open_to_relocation": open_to_relocation,
            },
            "classification": classification,
            "classification_reason": reason,
            "criteria_used": {
                "required_skills": self.criteria["required_skills"],
                "max_notice_period_days": self.criteria["max_notice_period_days"],
                "ctc_range_lpa": list(self.criteria["ctc_range_lpa"]),
            },
        }

        os.makedirs(RESULTS_DIR, exist_ok=True)
        filepath = os.path.join(RESULTS_DIR, f"{timestamp}_{safe_phone}.json")
        with open(filepath, "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Result saved: {filepath} | classification={classification}")

        count, csv_path = export_csv()
        logger.info(f"CSV updated: {csv_path} ({count} total records)")

        return f"Result saved to {filepath}."


class CandidateScreenerAgent(Agent):
    def __init__(self, candidate_name: str, role: str, criteria: dict) -> None:
        required_skills = ", ".join(criteria["required_skills"]) if criteria["required_skills"] else "any relevant skills"
        ctc_min, ctc_max = criteria["ctc_range_lpa"]

        super().__init__(
            instructions=f"""
You are Aria, an AI recruiter calling on behalf of a hiring company to conduct a brief phone screening.
You are calling {candidate_name} for the role of {role}.

Screening criteria (for your reference only — never share this with the candidate):
- Required skills (any one qualifies): {required_skills}
- Max notice period: {criteria["max_notice_period_days"]} days
- Expected CTC range: {ctc_min}–{ctc_max} LPA

--- OPENING ---
1. Greet the candidate by name and confirm identity: "Hi, am I speaking with {candidate_name}?"
2. If wrong person or unavailable: politely apologize, note you'll try again later, end the call. Log call_outcome as "not_available".
3. If correct person: introduce yourself — "Hi {candidate_name}, I'm Aria, an AI recruiter calling about a {role} opportunity. Do you have about 5 minutes?"
4. If they say no or to stop calling: apologize sincerely, end the call. Log call_outcome as "declined".

--- SCREENING QUESTIONS ---
Ask these one at a time in a natural, conversational tone. Do not rush.
1. "Could you tell me about your current role and how long you've been working in total?"
2. "What technologies or tools are you most comfortable working with?"
3. "What's your current notice period?"
4. "What's your current CTC, if you don't mind sharing?"
5. "And what would be your expected CTC for a new role?"
6. "Are you open to relocation, or would you prefer a remote setup?"

Allow natural follow-ups. If the candidate asks about the company or role, answer briefly and redirect back to screening.

--- HANDLING EDGE CASES ---
- If asked "Are you a bot / AI?": be honest — "Yes, I'm an AI assistant conducting the initial screening on behalf of the recruiting team. Would you like to continue?"
- If candidate wants to speak to a human: let them know the recruiting team will follow up directly.
- If the candidate is hostile or asks to stop: apologize and end the call, log as "declined".
- If there is long silence or you suspect voicemail: leave a brief message — "Hi {candidate_name}, this is Aria calling about a {role} opportunity. Please call us back at your convenience. Thank you!" — then log as "voicemail".

--- CLOSING ---
After collecting all answers, close warmly:
"That's everything I needed, {candidate_name}. Our recruiting team will review your profile and be in touch within 2–3 business days. Thanks so much for your time. Have a great day!"

Then immediately call submit_screening_result with all collected information. The candidate will not hear this — it is silent.
"""
        )


async def entrypoint(ctx: agents.JobContext):
    logger.info(f"Connecting to room: {ctx.room.name}")

    phone_number = None
    candidate_name = "there"
    role = "the open role"

    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
            candidate_name = data.get("candidate_name", "there")
            role = data.get("role", "the open role")
    except Exception:
        logger.warning("No valid JSON metadata found.")

    criteria = ROLE_CRITERIA.get(role, DEFAULT_CRITERIA)
    logger.info(f"Screening {candidate_name} for role: {role}")

    fnc_ctx = ScreeningTools(ctx, phone_number, candidate_name, role, criteria)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=_build_tts(),
        tools=fnc_ctx.flatten(),
    )

    await session.start(
        room=ctx.room,
        agent=CandidateScreenerAgent(candidate_name, role, criteria),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
            close_on_disconnect=True,
        ),
    )

    if phone_number:
        logger.info(f"Dialing {phone_number}...")
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=f"sip_{phone_number}",
                    wait_until_answered=True,
                )
            )
            logger.info("Call answered. Starting screening.")
            await session.generate_reply(
                instructions="The candidate has answered. Begin the opening sequence immediately."
            )
        except Exception as e:
            logger.error(f"Failed to place outbound call: {e}")
            ctx.shutdown()
    else:
        logger.info("No phone number in metadata. Treating as inbound/web call.")
        await session.generate_reply(instructions="Greet the candidate and begin the opening sequence.")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
        )
    )
