#!/usr/bin/env python3
"""Diagnostic script: test each step of the Slack file upload pipeline.

Usage:
    cd meow_me && uv run python scripts/test_upload.py

Reads SLACK_BOT_TOKEN from .env and tests:
  1. auth.test — verify token + print bot identity
  2. conversations.list — resolve #general to channel ID
  3. conversations.info — verify bot can see the channel
  4. files.getUploadURLExternal — get upload URL for a tiny test PNG
  5. Upload the test PNG
  6. files.completeUploadExternal — share the file to the channel
"""

import asyncio
import base64
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

SLACK_API = "https://slack.com/api"
CHANNEL_NAME = "general"  # Change this to test a different channel

# Minimal valid 1x1 transparent PNG (67 bytes)
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQAB"
    "Nl7BcQAAAABJRU5ErkJggg=="
)


def _header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ok(label: str, data: dict) -> bool:
    if data.get("ok"):
        print(f"  PASS  {label}")
        return True
    print(f"  FAIL  {label}: {data.get('error', 'unknown')}")
    print(f"        Full response: {data}")
    return False


async def main() -> None:
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        print("Error: SLACK_BOT_TOKEN not set in .env")
        sys.exit(1)

    print(f"\nSlack File Upload Diagnostic")
    print(f"Channel target: #{CHANNEL_NAME}")
    print(f"Token prefix: {token[:12]}...")
    print()

    async with httpx.AsyncClient() as client:
        # --- Step 1: auth.test ---
        print("Step 1: auth.test")
        r = await client.post(f"{SLACK_API}/auth.test", headers=_header(token))
        data = r.json()
        if _ok("auth.test", data):
            print(f"        bot_id={data.get('bot_id')}  user_id={data.get('user_id')}  team={data.get('team')}")

        # --- Step 2: conversations.list -> resolve channel name ---
        print("\nStep 2: conversations.list (resolve channel name)")
        channel_id = None
        cursor = ""
        page = 0
        while True:
            page += 1
            params = {"limit": "200", "types": "public_channel"}
            if cursor:
                params["cursor"] = cursor
            r = await client.get(
                f"{SLACK_API}/conversations.list",
                headers=_header(token),
                params=params,
            )
            data = r.json()
            if not _ok(f"conversations.list (page {page})", data):
                break
            for ch in data.get("channels", []):
                if ch.get("name") == CHANNEL_NAME:
                    channel_id = ch["id"]
                    is_member = ch.get("is_member", "?")
                    print(f"        Found #{CHANNEL_NAME} -> {channel_id}  is_member={is_member}")
                    break
            if channel_id:
                break
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                print(f"  FAIL  Channel #{CHANNEL_NAME} not found in workspace")
                break

        if not channel_id:
            print("\nCannot proceed without a channel ID.")
            sys.exit(1)

        # --- Step 3: conversations.info ---
        print(f"\nStep 3: conversations.info ({channel_id})")
        r = await client.get(
            f"{SLACK_API}/conversations.info",
            headers=_header(token),
            params={"channel": channel_id},
        )
        data = r.json()
        if _ok("conversations.info", data):
            ch = data.get("channel", {})
            print(f"        name={ch.get('name')}  is_member={ch.get('is_member')}  is_archived={ch.get('is_archived')}")

        # --- Step 4: files.getUploadURLExternal ---
        print(f"\nStep 4: files.getUploadURLExternal")
        r = await client.post(
            f"{SLACK_API}/files.getUploadURLExternal",
            headers=_header(token),
            data={"filename": "test_diagnostic.png", "length": len(TINY_PNG)},
        )
        data = r.json()
        if not _ok("files.getUploadURLExternal", data):
            sys.exit(1)
        upload_url = data["upload_url"]
        file_id = data["file_id"]
        print(f"        file_id={file_id}")
        print(f"        upload_url={upload_url[:80]}...")

        # --- Step 5: Upload the bytes ---
        print(f"\nStep 5: Upload {len(TINY_PNG)} bytes to upload URL")
        r = await client.post(
            upload_url,
            content=TINY_PNG,
            headers={"Content-Type": "application/octet-stream"},
        )
        print(f"        HTTP status: {r.status_code}")
        if r.status_code < 300:
            print(f"  PASS  File bytes uploaded")
        else:
            print(f"  FAIL  Upload returned {r.status_code}: {r.text[:200]}")
            sys.exit(1)

        # --- Step 6: files.completeUploadExternal ---
        print(f"\nStep 6: files.completeUploadExternal (channel_id={channel_id})")
        payload = {
            "files": [{"id": file_id, "title": "Diagnostic Test"}],
            "channel_id": channel_id,
            "initial_comment": "Diagnostic test upload from test_upload.py",
        }
        print(f"        Payload: {payload}")
        r = await client.post(
            f"{SLACK_API}/files.completeUploadExternal",
            headers={**_header(token), "Content-Type": "application/json"},
            json=payload,
        )
        data = r.json()
        if _ok("files.completeUploadExternal", data):
            print(f"        File shared to #{CHANNEL_NAME} successfully!")
        else:
            print(f"        HTTP status: {r.status_code}")

        # --- Step 7: Bonus — try conversations.join ---
        print(f"\nStep 7 (bonus): conversations.join ({channel_id})")
        r = await client.post(
            f"{SLACK_API}/conversations.join",
            headers={**_header(token), "Content-Type": "application/json"},
            json={"channel": channel_id},
        )
        data = r.json()
        if data.get("ok"):
            print(f"  PASS  conversations.join succeeded (bot joined or was already in channel)")
        elif data.get("error") == "method_not_allowed_for_channel_type":
            print(f"  INFO  conversations.join not allowed for this channel type")
        elif data.get("error") == "missing_scope":
            print(f"  INFO  channels:join scope not on bot token (not critical)")
        else:
            print(f"  FAIL  conversations.join: {data.get('error', 'unknown')}")
            print(f"        Full response: {data}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
