#!/usr/bin/env python3
"""
Batch operation examples using Open-PC SDK.

Batch operations execute atomically - if one step fails, the rest are skipped.
"""

import asyncio
from openpc_sdk import OpenPCClient
from openpc_sdk.batch import BatchExecutor


async def automated_browser_workflow():
    """Example: Automated browser navigation with form filling."""
    async with OpenPCClient() as client:
        executor = BatchExecutor(client)

        # Navigate to a site
        await client.open_url("https://example.com")

        # Wait for page load
        await client.wait(2.0)

        # Fill form using batch
        result = await executor.fill_form([
            {"text": "username@example.com", "key": "email"},
            {"text": "secret123", "key": "password"},
        ])

        print(f"Form fill result: {result}")


async def mouse_and_keyboard_combo():
    """Example: Combined mouse and keyboard operations."""
    async with OpenPCClient() as client:
        executor = BatchExecutor(client)

        # Move to position and click
        await executor.move_and_click(x=500, y=300, duration=0.5)

        # Type and press enter
        result = await executor.type_and_press(
            text="Hello World",
            key="enter"
        )

        print(f"Type and press result: {result}")


async def hotkey_sequence():
    """Example: Execute multiple hotkeys in sequence."""
    async with OpenPCClient() as client:
        executor = BatchExecutor(client)

        # Copy-paste sequence
        result = await executor.hotkey_sequence([
            ["ctrl", "c"],   # Copy
            ["tab"],         # Switch focus
            ["ctrl", "v"],   # Paste
            ["enter"],       # Confirm
        ], wait_between=0.3)

        print(f"Hotkey sequence result: {result}")


async def automated_test():
    """Example: Simple UI test pattern."""
    async with OpenPCClient() as client:
        executor = BatchExecutor(client)

        # Get initial screen info
        screen = await client.screen_info()
        print(f"Starting test on {screen.width}x{screen.height}")

        # Click specific location
        await executor.move_and_click(x=100, y=100)
        await client.wait(0.5)

        # Type expected value
        await executor.type_and_press(text="Expected value", key="enter")
        await client.wait(1.0)

        # Take screenshot for verification
        screenshot = await client.screenshot()
        if screenshot.success:
            print("Screenshot captured for verification")


async def main():
    """Run all examples."""
    print("=" * 50)
    print("Open-PC SDK Batch Operations")
    print("=" * 50)

    print("\n1. Running browser workflow...")
    try:
        await automated_browser_workflow()
    except Exception as e:
        print(f"Error: {e}")

    print("\n2. Running mouse/keyboard combo...")
    try:
        await mouse_and_keyboard_combo()
    except Exception as e:
        print(f"Error: {e}")

    print("\n3. Running hotkey sequence...")
    try:
        await hotkey_sequence()
    except Exception as e:
        print(f"Error: {e}")

    print("\n4. Running automated test...")
    try:
        await automated_test()
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
