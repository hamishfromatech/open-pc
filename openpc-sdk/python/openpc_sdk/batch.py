"""
Open-PC Batch Executor

Atomic batch operations for Open-PC desktop control.
"""

from typing import Any, Optional

from .client import OpenPCClient


class BatchExecutor:
    """
    Execute multiple operations atomically.

    Usage:
        async with OpenPCClient() as client:
            executor = BatchExecutor(client)
            results = await executor.execute([
                {"type": "type", "parameters": {"text": "Hello"}},
                {"type": "click", "parameters": {"x": 100, "y": 200}},
                {"type": "wait", "parameters": {"seconds": 1.0}},
            ])
    """

    def __init__(self, client: OpenPCClient):
        """Initialize batch executor with client."""
        self._client = client

    async def execute(
        self,
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Execute a batch of steps atomically.

        Args:
            steps: List of step dicts with 'type' and 'parameters'

        Returns:
            Result dict with 'success' and 'results'
        """
        return await self._client._request(
            "POST", "/batch",
            json_data={"steps": steps}
        )

    # ============== Convenience Builders ==============

    async def type_and_click(
        self,
        text: str,
        x: int,
        y: int,
        interval: float = 0.05,
        duration: float = 0.0,
    ) -> dict[str, Any]:
        """Type text then click at position."""
        steps = [
            {"type": "type", "parameters": {"text": text, "interval": interval}},
            {"type": "click", "parameters": {"x": x, "y": y, "duration": duration}},
        ]
        return await self.execute(steps)

    async def type_and_press(
        self,
        text: str,
        key: str,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        """Type text then press a key."""
        steps = [
            {"type": "type", "parameters": {"text": text, "interval": interval}},
            {"type": "press", "parameters": {"key": key}},
        ]
        return await self.execute(steps)

    async def move_and_click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
        duration: float = 0.5,
    ) -> dict[str, Any]:
        """Move to position then click."""
        steps = [
            {"type": "move_mouse", "parameters": {"x": x, "y": y, "duration": duration}},
            {"type": "click", "parameters": {"x": x, "y": y, "button": button, "clicks": clicks}},
        ]
        return await self.execute(steps)

    async def fill_form(
        self,
        fields: list[dict[str, Any]],
        submit_key: str = "enter",
    ) -> dict[str, Any]:
        """
        Fill multiple form fields.

        Args:
            fields: List of dicts with 'text' (field type) and 'key' (field name)
            submit_key: Key to press after filling
        """
        steps = []
        for field in fields:
            steps.append({
                "type": "type",
                "parameters": {"text": field["text"], "interval": 0.02}
            })
            steps.append({
                "type": "press",
                "parameters": {"key": "tab"}
            })

        steps.append({
            "type": "press",
            "parameters": {"key": submit_key}
        })

        return await self.execute(steps)

    async def locate_and_click(
        self,
        image_path: str,
        confidence: float = 0.9,
        click_offset_x: int = 0,
        click_offset_y: int = 0,
    ) -> dict[str, Any]:
        """Locate image on screen then click at that position."""
        steps = [
            {"type": "locate", "parameters": {"image_path": image_path, "confidence": confidence}},
            {"type": "click", "parameters": {
                "x_offset": click_offset_x,
                "y_offset": click_offset_y,
            }},
        ]
        return await self.execute(steps)

    async def wait_and_click(
        self,
        seconds: float,
        x: int,
        y: int,
    ) -> dict[str, Any]:
        """Wait then click at position."""
        steps = [
            {"type": "wait", "parameters": {"seconds": seconds}},
            {"type": "click", "parameters": {"x": x, "y": y}},
        ]
        return await self.execute(steps)

    async def hotkey_sequence(
        self,
        sequences: list[list[str]],
        wait_between: float = 0.5,
    ) -> dict[str, Any]:
        """
        Execute multiple hotkey sequences with optional waits.

        Args:
            sequences: List of key sequences (e.g., [['ctrl', 'c'], ['ctrl', 'v']])
            wait_between: Seconds to wait between sequences
        """
        steps = []
        for i, seq in enumerate(sequences):
            steps.append({
                "type": "hotkey",
                "parameters": {"keys": seq}
            })
            if wait_between > 0 and i < len(sequences) - 1:
                steps.append({
                    "type": "wait",
                    "parameters": {"seconds": wait_between}
                })

        return await self.execute(steps)
