#!/usr/bin/env python3
"""
Basic Open-PC SDK usage examples.

Run after starting Open-PC:
    docker-compose up -d
    python basic_usage.py
"""

import asyncio
import base64
from openpc_sdk import OpenPCClient, OpenPCError


async def main():
    # Initialize client (default: localhost:8090)
    async with OpenPCClient(host="localhost", port=8090) as client:
        # Check connection
        health = await client.health()
        print(f"Server status: {health.get('status')}")

        # Get screen info
        screen = await client.screen_info()
        print(f"Screen: {screen.width}x{screen.height}, cursor: ({screen.cursor_x}, {screen.cursor_y})")

        # Take screenshot
        screenshot = await client.screenshot()
        if screenshot.success:
            with open("screenshot.png", "wb") as f:
                f.write(base64.b64decode(screenshot.image_base64))
            print("Saved screenshot to screenshot.png")

        # Type text
        result = await client.type("Hello from Open-PC SDK!")
        print(f"Typing result: {result}")

        # Move and click
        result = await client.move_mouse(100, 100)
        print(f"Mouse moved: {result}")

        result = await client.click(button="left")
        print(f"Click result: {result}")

        # Press hotkey (Ctrl+C)
        result = await client.hotkey(["ctrl", "c"])
        print(f"Hotkey result: {result}")

        # List windows
        windows = await client.list_windows()
        print(f"Open windows: {[w.title for w in windows]}")

        # Run command
        result = await client.run_command("echo 'Hello from container'")
        print(f"Command output: {result.output}")


if __name__ == "__main__":
    asyncio.run(main())
