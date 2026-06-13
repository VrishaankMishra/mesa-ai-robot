"""Voice assistant response logic (VOX-003).

Turns a :class:`ParsedIntent` into a spoken-response string, consulting the database for
medication facts. Pure with respect to time (pass ``now``) and side effects (alerts go
through an injected ``alert_fn``), so it's fully unit-testable. The TTS layer just speaks
whatever string this returns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from mesa.audio.intents import Intent, ParsedIntent
from mesa.data.database import Database


def pretty_med(name: str) -> str:
    """'vitamin_d' -> 'Vitamin D'."""
    return name.replace("_", " ").title()


def next_scheduled(schedule: list[dict], current_hhmm: str) -> dict | None:
    """First schedule entry strictly after ``current_hhmm`` ("HH:MM"). None if none left."""
    upcoming = [s for s in schedule if s["time_of_day"] > current_hhmm]
    return min(upcoming, key=lambda s: s["time_of_day"]) if upcoming else None


class VoiceAssistant:
    def __init__(self, db: Database, alert_fn: Callable[[str], None] | None = None):
        self.db = db
        self.alert_fn = alert_fn

    def _known_meds(self) -> set[str]:
        names = {m["name"] for m in self.db.list_medications(active_only=False)}
        names |= {s["med_name"] for s in self.db.get_schedule()}
        return names

    def respond(self, parsed: ParsedIntent, now: float | None = None) -> str:
        now = now if now is not None else datetime.now().timestamp()
        dt = datetime.fromtimestamp(now)

        if parsed.intent == Intent.HELP:
            self.db.log_event("help_request", detail="voice command", ts=now)
            if self.alert_fn is not None:
                self.alert_fn("MeSA user requested help.")
            return "Okay, I'm calling for help now."

        if parsed.intent == Intent.DATE_TIME:
            return dt.strftime("It is %A, %B %-d, and the time is %-I:%M %p.")

        if parsed.intent == Intent.DID_I_TAKE:
            if not parsed.med:
                return "Which medication do you mean?"
            if parsed.med not in self._known_meds():
                return f"I don't have a medication called {pretty_med(parsed.med)}."
            taken = self.db.meds_taken_today(now=now)
            if parsed.med in taken:
                return f"Yes, you've taken {pretty_med(parsed.med)} today."
            return f"No, you haven't taken {pretty_med(parsed.med)} yet today."

        if parsed.intent == Intent.NEXT_MED:
            schedule = [dict(s) for s in self.db.get_schedule()]
            nxt = next_scheduled(schedule, dt.strftime("%H:%M"))
            if nxt is None:
                return "You have no more medications scheduled today."
            dose = f" ({nxt['dose']})" if nxt.get("dose") else ""
            return f"Your next medication is {pretty_med(nxt['med_name'])} at {nxt['time_of_day']}{dose}."

        return "Sorry, I didn't catch that. Please say it again."
