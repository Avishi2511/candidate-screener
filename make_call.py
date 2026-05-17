import argparse
import asyncio
import os
import random
import json
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")


async def main():
    parser = argparse.ArgumentParser(description="Dispatch an outbound screening call via LiveKit.")
    parser.add_argument("--to", required=True, help="Phone number to call (e.g. +91...)")
    parser.add_argument("--name", required=True, help="Candidate's full name (e.g. 'Rahul Sharma')")
    parser.add_argument("--role", required=True, help="Role being screened for (e.g. 'Backend Engineer')")
    args = parser.parse_args()

    phone_number = args.to.strip()
    if not phone_number.startswith("+"):
        print("Error: Phone number must start with '+' and country code.")
        return

    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not (url and api_key and api_secret):
        print("Error: LiveKit credentials missing in .env")
        return

    lk_api = api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)

    room_name = f"screen-{phone_number.replace('+', '')}-{random.randint(1000, 9999)}"

    print(f"Initiating screening call to {args.name} ({phone_number}) for {args.role}...")
    print(f"Room: {room_name}")

    try:
        dispatch_request = api.CreateAgentDispatchRequest(
            agent_name="outbound-caller",
            room=room_name,
            metadata=json.dumps({
                "phone_number": phone_number,
                "candidate_name": args.name,
                "role": args.role,
            }),
        )

        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_request)

        print("\n✅ Call dispatched successfully!")
        print(f"Dispatch ID: {dispatch.id}")
        print("-" * 40)
        print("The agent is joining the room and will dial the candidate.")
        print("Check your agent terminal for live logs.")

    except Exception as e:
        print(f"\n❌ Error dispatching call: {e}")

    finally:
        await lk_api.aclose()


if __name__ == "__main__":
    asyncio.run(main())
