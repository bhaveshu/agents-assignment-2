"""
Option A: Calendar Assistant Tools

Implement Google Calendar operations for listing events, finding available slots,
creating events, checking conflicts, and rescheduling events.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any, Optional

_pkg_dir = str(Path(__file__).parent.parent.resolve())
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

try:
    from tools.auth import get_calendar_service
except ImportError:
    from workspace_assistant.tools.auth import get_calendar_service


def _parse_iso_datetime(dt_str: str) -> datetime.datetime:
    """Parse ISO datetime string, adding local/UTC timezone if naive."""
    dt_str = dt_str.strip()
    # Replace space with T for ISO format
    if " " in dt_str and "T" not in dt_str:
        dt_str = dt_str.replace(" ", "T")

    # If only date is provided (YYYY-MM-DD), append midnight
    if len(dt_str) == 10 and dt_str.count("-") == 2:
        dt_str += "T00:00:00"

    # Support 'Z' as UTC
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"

    dt = datetime.datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        # Default to UTC if naive
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def list_upcoming_events(
    max_results: int = 10,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
) -> dict[str, Any]:
    """List upcoming events from the user's primary Google Calendar.

    Use this tool when the user asks to see their upcoming schedule, check meetings
    for today, tomorrow, or a specific date range, or view existing appointments.

    Args:
        max_results: Maximum number of events to return (default 10).
        time_min: ISO 8601 start time (e.g., '2026-10-10T09:00:00Z'). Defaults to current time.
        time_max: ISO 8601 end time boundary (e.g., '2026-10-15T18:00:00Z').

    Returns:
        A dict with 'status': 'success' and 'events': list of event details,
        or 'status': 'error' and 'message' describing the issue.
    """
    try:
        service = get_calendar_service()

        if time_min:
            min_dt = _parse_iso_datetime(time_min)
        else:
            min_dt = datetime.datetime.now(datetime.timezone.utc)
        min_iso = min_dt.isoformat()

        max_iso = None
        if time_max:
            max_dt = _parse_iso_datetime(time_max)
            max_iso = max_dt.isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=min_iso,
                timeMax=max_iso,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = events_result.get("items", [])
        events = []
        for item in items:
            start = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
            end = item.get("end", {}).get("dateTime", item.get("end", {}).get("date"))
            events.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary", "(No title)"),
                    "start": start,
                    "end": end,
                    "location": item.get("location", ""),
                    "description": item.get("description", ""),
                    "status": item.get("status", ""),
                    "html_link": item.get("htmlLink", ""),
                }
            )

        return {
            "status": "success",
            "count": len(events),
            "events": events,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to list events: {str(e)}"}


def check_conflicts(start_time: str, end_time: str) -> dict[str, Any]:
    """Check for any scheduling conflicts in the primary calendar within a time range.

    Use this tool before creating or rescheduling a meeting to verify whether the
    user already has another appointment or overlapping commitment.

    Args:
        start_time: Proposed meeting start time in ISO 8601 format (e.g., '2026-10-12T14:00:00Z').
        end_time: Proposed meeting end time in ISO 8601 format (e.g., '2026-10-12T15:00:00Z').

    Returns:
        A dict with 'status': 'success', 'has_conflicts': bool, and 'conflicts': list of overlapping events,
        or 'status': 'error' and 'message' describing the issue.
    """
    try:
        start_dt = _parse_iso_datetime(start_time)
        end_dt = _parse_iso_datetime(end_time)

        if end_dt <= start_dt:
            return {
                "status": "error",
                "message": "end_time must be strictly after start_time.",
            }

        service = get_calendar_service()
        # Query calendar with buffer around start and end
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = events_result.get("items", [])
        conflicts = []
        for item in items:
            item_start_raw = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
            item_end_raw = item.get("end", {}).get("dateTime", item.get("end", {}).get("date"))
            if not item_start_raw or not item_end_raw:
                continue

            item_start = _parse_iso_datetime(item_start_raw)
            item_end = _parse_iso_datetime(item_end_raw)

            # Check overlap: start < item_end and end > item_start
            if start_dt < item_end and end_dt > item_start:
                conflicts.append(
                    {
                        "id": item.get("id"),
                        "summary": item.get("summary", "(No title)"),
                        "start": item_start_raw,
                        "end": item_end_raw,
                        "location": item.get("location", ""),
                    }
                )

        return {
            "status": "success",
            "has_conflicts": len(conflicts) > 0,
            "count": len(conflicts),
            "conflicts": conflicts,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to check conflicts: {str(e)}"}


def find_available_slots(
    start_date: str,
    end_date: str,
    duration_minutes: int = 60,
    working_hours_start: int = 9,
    working_hours_end: int = 17,
) -> dict[str, Any]:
    """Find free, available time slots during working hours within a date range.

    Use this tool when the user asks to find free time, look for open slots,
    or schedule a meeting without having a specific time in mind.

    Args:
        start_date: Search start date (e.g., '2026-10-12' or '2026-10-12T09:00:00Z').
        end_date: Search end date (e.g., '2026-10-16' or '2026-10-16T17:00:00Z').
        duration_minutes: Required meeting duration in minutes (default 60).
        working_hours_start: Daily start hour in 24h format (e.g., 9 for 9:00 AM).
        working_hours_end: Daily end hour in 24h format (e.g., 17 for 5:00 PM).

    Returns:
        A dict with 'status': 'success' and 'available_slots': list of slot objects with 'start' and 'end',
        or 'status': 'error' and 'message' describing the issue.
    """
    try:
        start_dt = _parse_iso_datetime(start_date)
        end_dt = _parse_iso_datetime(end_date)
        tz = start_dt.tzinfo or datetime.timezone.utc

        if end_dt <= start_dt:
            return {
                "status": "error",
                "message": "end_date must be strictly after start_date.",
            }

        service = get_calendar_service()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        busy_events: list[tuple[datetime.datetime, datetime.datetime]] = []
        for item in events_result.get("items", []):
            item_start_raw = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
            item_end_raw = item.get("end", {}).get("dateTime", item.get("end", {}).get("date"))
            if item_start_raw and item_end_raw:
                s = _parse_iso_datetime(item_start_raw)
                e = _parse_iso_datetime(item_end_raw)
                busy_events.append((s, e))

        available_slots = []
        current_day = start_dt.date()
        end_day = end_dt.date()
        slot_delta = datetime.timedelta(minutes=duration_minutes)

        while current_day <= end_day:
            # Skip Saturday (5) and Sunday (6) by default
            if current_day.weekday() < 5:
                day_start = datetime.datetime.combine(
                    current_day,
                    datetime.time(hour=working_hours_start, minute=0),
                    tzinfo=tz,
                )
                day_end = datetime.datetime.combine(
                    current_day,
                    datetime.time(hour=working_hours_end, minute=0),
                    tzinfo=tz,
                )

                candidate_start = max(day_start, start_dt)
                while candidate_start + slot_delta <= min(day_end, end_dt):
                    candidate_end = candidate_start + slot_delta
                    # Check if candidate overlaps with any busy event
                    is_busy = False
                    for b_start, b_end in busy_events:
                        if candidate_start < b_end and candidate_end > b_start:
                            is_busy = True
                            # Jump candidate_start to the end of the conflict
                            candidate_start = max(candidate_start + datetime.timedelta(minutes=30), b_end)
                            break

                    if not is_busy:
                        available_slots.append(
                            {
                                "start": candidate_start.isoformat(),
                                "end": candidate_end.isoformat(),
                            }
                        )
                        # Advance candidate by 30 mins or duration
                        candidate_start += datetime.timedelta(minutes=30)

            current_day += datetime.timedelta(days=1)

        return {
            "status": "success",
            "duration_minutes": duration_minutes,
            "count": len(available_slots),
            "available_slots": available_slots[:20],  # Return up to 20 best candidate slots
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to find available slots: {str(e)}"}


def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create and schedule a new event on the user's primary Google Calendar.

    Use this tool when the user wants to schedule a meeting, create an appointment,
    or add an event to their calendar.

    Args:
        summary: Title or summary of the event (e.g., 'Weekly Team Sync').
        start_time: Event start time in ISO 8601 format (e.g., '2026-10-12T10:00:00Z').
        end_time: Event end time in ISO 8601 format (e.g., '2026-10-12T11:00:00Z').
        description: Optional notes, agenda, or description for the event.
        location: Optional location or video call link (e.g., 'Conference Room B' or 'Google Meet').
        attendees: Optional list of attendee email addresses.

    Returns:
        A dict with 'status': 'success', 'event_id': str, 'html_link': str, and event details,
        or 'status': 'error' and 'message' describing the issue.
    """
    try:
        start_dt = _parse_iso_datetime(start_time)
        end_dt = _parse_iso_datetime(end_time)

        if end_dt <= start_dt:
            return {
                "status": "error",
                "message": "end_time must be strictly after start_time.",
            }

        service = get_calendar_service()

        event_body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
        }

        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [{"email": a.strip()} for a in attendees if a.strip()]

        created_event = service.events().insert(calendarId="primary", body=event_body).execute()

        return {
            "status": "success",
            "event_id": created_event.get("id"),
            "summary": created_event.get("summary"),
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "html_link": created_event.get("htmlLink", ""),
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to create event: {str(e)}"}


def reschedule_event(
    event_id: str,
    new_start_time: str,
    new_end_time: str,
) -> dict[str, Any]:
    """Reschedule an existing calendar event to a new start and end time.

    Use this tool when the user wants to move, postpone, or change the time of
    an existing meeting.

    Args:
        event_id: The unique ID of the event to reschedule.
        new_start_time: New event start time in ISO 8601 format (e.g., '2026-10-12T15:00:00Z').
        new_end_time: New event end time in ISO 8601 format (e.g., '2026-10-12T16:00:00Z').

    Returns:
        A dict with 'status': 'success', 'event_id': str, 'summary': str, and updated times,
        or 'status': 'error' and 'message' describing the issue.
    """
    try:
        new_start_dt = _parse_iso_datetime(new_start_time)
        new_end_dt = _parse_iso_datetime(new_end_time)

        if new_end_dt <= new_start_dt:
            return {
                "status": "error",
                "message": "new_end_time must be strictly after new_start_time.",
            }

        service = get_calendar_service()

        # Retrieve existing event to preserve description, summary, attendees, etc.
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        event["start"] = {"dateTime": new_start_dt.isoformat()}
        event["end"] = {"dateTime": new_end_dt.isoformat()}

        updated_event = (
            service.events()
            .update(calendarId="primary", eventId=event_id, body=event)
            .execute()
        )

        return {
            "status": "success",
            "event_id": updated_event.get("id"),
            "summary": updated_event.get("summary"),
            "new_start": new_start_dt.isoformat(),
            "new_end": new_end_dt.isoformat(),
            "html_link": updated_event.get("htmlLink", ""),
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to reschedule event: {str(e)}"}


# Export the list of calendar tools for the agent and testing
calendar_tools = [
    list_upcoming_events,
    find_available_slots,
    create_event,
    check_conflicts,
    reschedule_event,
]
