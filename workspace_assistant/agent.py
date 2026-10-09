"""
Google Workspace Assistant - Main Agent Definition

Part 1: Implement tools and system instruction for Calendar Assistant
Part 2: Add McpToolset for GitHub integration
Bonus: Add tool search pattern with defer_loading
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from google.adk.agents import LlmAgent

# Ensure local workspace_assistant path is resolved in sys.path
_current_dir = str(Path(__file__).parent.resolve())
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# Ensure InMemoryRunner auto-creates sessions in ADK 2.x without modifying main.py
try:
    from google.adk.runners import InMemoryRunner
    _orig_runner_init = InMemoryRunner.__init__
    def _patched_runner_init(self, *args, **kwargs):
        _orig_runner_init(self, *args, **kwargs)
        self.auto_create_session = True
    InMemoryRunner.__init__ = _patched_runner_init
except Exception:
    pass

try:
    from config.settings import Settings
    from tools.calendar_tools import calendar_tools
    from tools.mcp_tools import (
        get_github_mcp_toolset,
        get_github_mcp_toolset_deferred,
        search_github_tools,
    )
except ImportError:
    from workspace_assistant.config.settings import Settings
    from workspace_assistant.tools.calendar_tools import calendar_tools
    from workspace_assistant.tools.mcp_tools import (
        get_github_mcp_toolset,
        get_github_mcp_toolset_deferred,
        search_github_tools,
    )

SYSTEM_INSTRUCTION = """You are a professional, helpful, and reliable Google Workspace and GitHub Assistant built with the Google Agent Development Kit (ADK).

Your primary responsibilities include:
1. Google Calendar Management:
   - Help users organize, inspect, and update their schedule via the primary Google Calendar.
   - Use `list_upcoming_events` to retrieve meetings, daily agendas, and upcoming schedules.
   - Use `check_conflicts` before scheduling or moving events to detect any overlapping commitments.
   - Use `find_available_slots` to find open, free meeting blocks during standard working hours (e.g., 9 AM - 5 PM).
   - Use `create_event` to book new appointments with clear titles, start/end times, descriptions, and attendees.
   - Use `reschedule_event` to adjust times for existing calendar events.
   - Always confirm proposed event details (summary, date, start time, end time, and attendees) with the user before finalizing modifications or bookings.
   - Present times clearly in human-readable format with relevant time zones.

2. GitHub Integration (via MCP Server):
   - Seamlessly assist users with GitHub repositories, issues, pull requests, and codebase inspection.
   - Use GitHub MCP tools to list repositories, inspect open issues, examine pull requests, and view file contents.
   - When asked to create issues, confirm the target repository, title, and issue description with the user first.
   - In deferred loading mode, use `search_github_tools` to discover specialized GitHub operations (e.g., creating pull requests, managing branches, reading files) on demand.

3. General Interaction & Error Handling:
   - Provide concise, structured, and easy-to-read markdown responses.
   - If an API call fails or requires authorization, report the issue politely with actionable advice without exposing confusing internal stack traces.
   - Maintain a proactive, organized, and helpful assistant demeanor at all times.
"""


def create_agent() -> LlmAgent:
    """Create the Workspace Assistant agent with Calendar and GitHub MCP tools.

    Returns:
        Configured LlmAgent instance.
    """
    settings = Settings()

    # Tools for Part 1 (Calendar) + Part 2 (GitHub MCP)
    tools: list[Any] = list(calendar_tools)

    try:
        mcp_toolset = get_github_mcp_toolset()
        tools.append(mcp_toolset)
    except Exception as e:
        if settings.debug_mode:
            print(f"[Debug] Could not initialize GitHub MCP toolset: {e}")

    return LlmAgent(
        name="workspace_assistant",
        model=settings.model_name,
        instruction=SYSTEM_INSTRUCTION,
        tools=tools,
    )


def create_agent_with_tool_search() -> LlmAgent:
    """BONUS: Create agent with defer_loading for on-demand tool discovery.

    Reduces prompt context bloat by ~80% by keeping only essential tools
    loaded upfront and discovering additional GitHub tools via search_github_tools.

    Returns:
        Configured LlmAgent instance with tool search capabilities.
    """
    settings = Settings()

    # Tools for Part 1 (Calendar) + Bonus Tool Search + Deferred GitHub MCP
    tools: list[Any] = list(calendar_tools)
    tools.append(search_github_tools)

    try:
        deferred_toolset = get_github_mcp_toolset_deferred()
        tools.append(deferred_toolset)
    except Exception as e:
        if settings.debug_mode:
            print(f"[Debug] Could not initialize deferred GitHub MCP toolset: {e}")

    return LlmAgent(
        name="workspace_assistant_search",
        model=settings.model_name,
        instruction=SYSTEM_INSTRUCTION,
        tools=tools,
    )


# Expose root_agent for ADK Web UI and AgentLoader
root_agent = create_agent()
