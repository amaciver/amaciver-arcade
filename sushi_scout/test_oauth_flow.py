#!/usr/bin/env python3
"""Interactive test of the full OAuth flow via STDIO MCP transport.

How it works:
1. Starts the MCP server in STDIO mode
2. Calls GetUserProfile (requires Google OAuth with userinfo.email scope)
3. Arcade returns an authorization URL -> opens in your browser
4. You complete the Google login and grant permissions
5. Script re-calls the tool -> Arcade now has the token -> returns profile

Usage:
    cd sushi_scout
    uv run python test_oauth_flow.py
"""

import json
import subprocess
import sys
import threading
import time
import webbrowser

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def start_server():
    """Start MCP server as subprocess."""
    print("Starting MCP server (STDIO transport)...")
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        ["uv", "run", "arcade", "mcp", "stdio", "--package", "sushi_scout"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    # Capture stderr in background
    stderr_lines = []

    def read_stderr():
        for line in proc.stderr:
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                stderr_lines.append(text)

    t = threading.Thread(target=read_stderr, daemon=True)
    t.start()

    return proc, stderr_lines


def send_mcp(proc, msg):
    """Send a JSON-RPC message (newline-delimited JSON)."""
    data = json.dumps(msg) + "\n"
    proc.stdin.write(data.encode())
    proc.stdin.flush()


def recv_mcp(proc, timeout_sec=60):
    """Receive a JSON-RPC response (newline-delimited JSON)."""
    import os

    # Use non-blocking reads with a polling loop
    os.set_blocking(proc.stdout.fileno(), False)
    buf = b""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            chunk = proc.stdout.read(4096)
            if chunk:
                buf += chunk
                # Check if we have a complete JSON line
                if b"\n" in buf:
                    line = buf.split(b"\n")[0]
                    return json.loads(line)
        except (BlockingIOError, TypeError):
            pass
        time.sleep(0.2)
    return None


def extract_auth_url(resp):
    """Extract authorization URL from an MCP tool response."""
    result = resp.get("result", {})
    structured = result.get("structuredContent", {})

    # Direct field
    if structured.get("authorization_url"):
        return structured["authorization_url"]

    # Check in content text (Arcade wraps it as JSON in content[0].text)
    for item in result.get("content", []):
        text = item.get("text", "")
        try:
            parsed = json.loads(text)
            if parsed.get("authorization_url"):
                return parsed["authorization_url"]
        except (json.JSONDecodeError, AttributeError):
            pass
        # Also look for raw URLs in the message text
        if "arcade.dev" in text or "accounts.google" in text:
            for word in text.split():
                if word.startswith("http"):
                    return word.rstrip(".")

    return None


def print_profile(resp):
    """Pretty-print user profile from MCP response."""
    result = resp.get("result", {})
    structured = result.get("structuredContent", {})

    email = structured.get("email")
    name = structured.get("name")
    if email or name:
        print(f"\n   Profile retrieved successfully!")
        print(f"   Name:     {name or 'N/A'}")
        print(f"   Email:    {email or 'N/A'}")
        print(f"   Verified: {structured.get('verified', 'N/A')}")
        return True

    # Also check content text
    for item in result.get("content", []):
        text = item.get("text", "")
        try:
            parsed = json.loads(text)
            if parsed.get("email"):
                print(f"\n   Profile retrieved successfully!")
                print(f"   Name:     {parsed.get('name', 'N/A')}")
                print(f"   Email:    {parsed.get('email', 'N/A')}")
                print(f"   Verified: {parsed.get('verified', 'N/A')}")
                return True
        except (json.JSONDecodeError, AttributeError):
            pass

    return False


def main():
    proc, stderr_lines = start_server()
    time.sleep(2)

    try:
        # Step 1: Initialize MCP session
        print("\n1. Initializing MCP session...")
        send_mcp(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "sushi-scout-test", "version": "1.0"},
            },
        })
        resp = recv_mcp(proc, timeout_sec=10)
        if resp and "result" in resp:
            print("   OK - session initialized")
        else:
            print(f"   FAILED: {resp}")
            return

        send_mcp(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        time.sleep(1)

        # Step 2: Call GetUserProfile (triggers Google OAuth)
        profile_params = {
            "name": "SushiScout_GetUserProfile",
            "arguments": {},
        }

        print("\n2. Calling GetUserProfile...")
        print("   This tool requires Google OAuth (userinfo.email scope).\n")

        send_mcp(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": profile_params,
        })

        resp = recv_mcp(proc, timeout_sec=30)
        if not resp:
            print("   Timed out. Server logs:")
            for line in stderr_lines[-10:]:
                print(f"   {line}")
            return

        # Check if we got an auth URL
        auth_url = extract_auth_url(resp)
        is_error = resp.get("result", {}).get("isError", False)

        if auth_url:
            print("   Authorization required!")
            print(f"   Opening browser: {auth_url}\n")
            webbrowser.open(auth_url)
            print("   >> Complete the Google login in your browser <<")
            print("   >> Then press ENTER here to continue <<\n")
            input("   Press ENTER after authorizing...")

            # Step 3: Re-call the same tool (now authorized)
            print("\n3. Re-calling GetUserProfile (now authorized)...")
            send_mcp(proc, {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": profile_params,
            })
            resp = recv_mcp(proc, timeout_sec=30)

        elif is_error:
            result = resp.get("result", {})
            for item in result.get("content", []):
                text = item.get("text", "")
                try:
                    parsed = json.loads(text)
                    msg = parsed.get("message", text)
                except (json.JSONDecodeError, AttributeError):
                    msg = text
                print(f"   {msg}")
            return

        # Step 4: Show results
        if resp:
            print("\n" + "=" * 60)
            if not print_profile(resp):
                print("   Raw response:")
                print(json.dumps(resp, indent=2)[:2000])
            print("=" * 60)
            print("\nOAuth flow test complete!")
        else:
            print("\n   No response after authorization. Check server logs:")
            for line in stderr_lines[-10:]:
                print(f"   {line}")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("Server stopped.")


if __name__ == "__main__":
    main()
