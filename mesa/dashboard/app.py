"""Streamlit dashboard (DASH-001).

Shows today's medication status (taken/missed) and a live event-history table read from
SQLite. Run with:

    streamlit run mesa/dashboard/app.py

Data-prep logic lives in mesa.engine.compliance.compute_med_status (unit-tested); this
module is just the view layer.
"""

from __future__ import annotations

from mesa.data.database import Database, iso
from mesa.engine.compliance import compute_med_status


def render() -> None:
    import streamlit as st  # imported lazily so importing this module needs no streamlit

    st.set_page_config(page_title="MeSA 2.0", page_icon="💊", layout="wide")
    st.title("💊 MeSA 2.0 — Medication & Safety Dashboard")
    st.caption("Assistive aid, not a medical device.")

    db = Database()  # events.db at repo root

    schedule = [dict(r) for r in db.get_schedule()]
    taken_today = db.meds_taken_today()
    statuses = compute_med_status(schedule, taken_today)

    st.subheader("Today's medications")
    if not statuses:
        st.info("No schedule yet. Add medications + schedule rows (Week 3, ENG-001).")
    else:
        cols = st.columns(len(statuses))
        for col, s in zip(cols, statuses):
            mark = "✅ Taken" if s.taken else "⏳ Not yet"
            col.metric(label=f"{s.time_of_day} · {s.med_name}", value=mark,
                       delta=s.dose or "", delta_color="off")

    st.subheader("Recent events")
    events = db.get_events(limit=50)
    if not events:
        st.write("No events logged yet.")
    else:
        st.dataframe(
            [
                {
                    "time": iso(e["ts"]),
                    "type": e["type"],
                    "medication": e["med_name"] or "",
                    "detail": e["detail"] or "",
                }
                for e in events
            ],
            use_container_width=True,
            hide_index=True,
        )

    db.close()


if __name__ == "__main__":
    render()
