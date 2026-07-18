"""MeSA 2.0 orchestrator entry point (ENG-004).

Builds the event bus + decision engine from config and, in ``--live`` mode, starts the
vision worker (camera → posture/detection events) and — when a Vosk model is present —
the audio worker (mic → voice commands + acknowledge/help events). The decision engine
consumes the bus on the main thread until Ctrl-C.

``--demo`` instead pushes a synthetic event sequence through the engine so the integrated
decision logic can be exercised on any laptop with no camera or mic.

    python main.py --demo          # synthetic events, no hardware
    python main.py --live          # camera (+ mic if a Vosk model is downloaded)
    python main.py --live --echo   # print speech instead of TTS
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa import __version__
from mesa.config import get, load_config
from mesa.data.database import Database
from mesa.engine.compliance import ComplianceTracker
from mesa.engine.decision import DecisionEngine
from mesa.engine.escalation import EscalationMachine
from mesa.engine.events import (
    ACKNOWLEDGE,
    BOTTLE_OBSERVATION,
    POSTURE,
    Event,
    EventBus,
)
from mesa.engine.inactivity import InactivityMonitor
from mesa.hardware.oled import face_for
from mesa.hardware.outputs import build_output_hub
from mesa.vision.posture import Posture, PostureMonitor


def build_engine(db: Database, cfg: dict, speak=None, set_emotion=None, notify=None) -> DecisionEngine:
    compliance = ComplianceTracker(
        db,
        debounce_seconds=get(cfg, "compliance.absence_debounce_seconds", 3),
        taken_after_absent_seconds=get(cfg, "compliance.taken_after_absent_seconds", 10),
    )
    notify = notify or (lambda r: print(f"[ntfy] {r}"))
    escalation = EscalationMachine(
        l1_wait_seconds=get(cfg, "escalation.l1_wait_seconds", 60),
        on_check_in=lambda r: (speak or print)(f"Are you okay? ({r})"),
        on_notify=lambda r: notify(f"MeSA check-in unanswered: {r}"),
        on_caregiver=lambda r: notify(f"CAREGIVER ALERT — please check in now: {r}"),
        db=db,
    )
    return DecisionEngine(
        db,
        compliance,
        escalation,
        posture_monitor=PostureMonitor(get(cfg, "pose.lying_trigger_seconds", 30)),
        inactivity_monitor=InactivityMonitor(get(cfg, "escalation.inactivity_window_seconds", 3600)),
        speak=speak,
        set_emotion=set_emotion,
    )


def _demo(engine: DecisionEngine, hub=None) -> None:
    print("\n--- demo: synthetic event sequence ---")
    # Bottle removed then returned after 12s -> 'taken' event.
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": False}, ts=0))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": False}, ts=4))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": True}, ts=14))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": True}, ts=18))
    # Lying for >30s -> possible_fall -> escalation L1; no ack for 60s -> L2.
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=100))
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=131))
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=200))
    print(f"escalation level after no response: {engine.escalation.level.value}")
    if hub is not None:  # OLED face followed the fall into ALERT (Null display on laptop)
        print(f"OLED face on alert: {hub.emotions.current.value} {face_for(hub.emotions.current)}")
    # User responds.
    engine.process_event(Event(ACKNOWLEDGE, {}, ts=205))
    print(f"escalation level after acknowledge: {engine.escalation.level.value}")
    if hub is not None:
        print(f"OLED face after acknowledge: {hub.emotions.current.value} {face_for(hub.emotions.current)}")
    print("events logged:", [(e["type"], e["med_name"], e["detail"]) for e in engine.db.get_events()])


def _live(engine: DecisionEngine, db: Database, cfg: dict, echo: bool) -> None:
    """Start the vision (+ audio, if a Vosk model exists) workers and consume the bus."""
    from mesa.vision.worker import VisionWorker

    bus = EventBus()
    workers = []

    # Open the camera on the main thread: macOS can only show the one-time camera
    # permission dialog here — doing it inside the worker thread aborts the process.
    import cv2

    camera_index = get(cfg, "vision.camera_index", 0)
    capture = cv2.VideoCapture(camera_index)
    if capture.isOpened():
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, get(cfg, "vision.frame_width", 640))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, get(cfg, "vision.frame_height", 480))
        model_path = Path(get(cfg, "detection.model_path", "models/best.pt"))
        known_meds = {m["name"] for m in db.list_medications(active_only=False)}
        known_meds |= {s["med_name"] for s in db.get_schedule()}
        if not model_path.exists():
            print(f"[live] no trained detector at {model_path} — MED detection off, posture only.")
        workers.append(VisionWorker(bus, cfg, known_meds=known_meds,
                                    model_available=model_path.exists(), capture=capture))
    else:
        capture.release()
        print(f"[live] camera {camera_index} unavailable — vision off "
              "(check the connection and camera permissions).")

    vosk_path = Path(get(cfg, "voice.vosk_model_path", "models/vosk-model-small-en-us"))
    if vosk_path.exists():
        from mesa.audio.assistant import VoiceAssistant
        from mesa.audio.stt import VoskRecognizer
        from mesa.audio.worker import AudioWorker
        from mesa.alerts.ntfy import send_alert
        from mesa.audio.tts import speak as tts_speak

        topic = get(cfg, "alerts.ntfy_topic", "")
        assistant = VoiceAssistant(
            db, alert_fn=lambda msg: send_alert(topic, msg, title="MeSA help")
        )
        workers.append(AudioWorker(
            bus, assistant, VoskRecognizer(str(vosk_path)),
            wake_word=get(cfg, "voice.wake_word", "mesa"),
            speak=lambda msg: tts_speak(msg, echo=echo),
        ))
    else:
        print(f"[live] no Vosk model at {vosk_path} — voice off (see models/README.md).")

    if not workers:
        print("[live] no camera and no Vosk model — nothing to run.")
        return
    for w in workers:
        w.start()
    print(f"[live] running with {', '.join(w.name for w in workers)}. Ctrl-C to stop.")
    try:
        engine.run(bus)
    except KeyboardInterrupt:
        print("\n[live] stopping…")
    finally:
        for w in workers:
            w.stop()
        bus.shutdown()


def main() -> None:
    p = argparse.ArgumentParser(description="MeSA orchestrator")
    p.add_argument("--demo", action="store_true", help="run a synthetic event sequence")
    p.add_argument("--live", action="store_true", help="start camera/mic workers")
    p.add_argument("--echo", action="store_true", help="print speech instead of TTS")
    args = p.parse_args()

    cfg = load_config()
    print(f"MeSA {__version__} — orchestrator ready.")
    db = Database(":memory:" if args.demo else "events.db")
    # Output hub (OLED face + pan/tilt head); Null drivers on a laptop, real on the Pi.
    hub = build_output_hub(cfg)
    speak = notify = None
    if args.live:
        from mesa.alerts.ntfy import send_alert
        from mesa.audio.tts import speak as tts_speak

        speak = lambda msg: tts_speak(msg, echo=args.echo)  # noqa: E731
        topic = get(cfg, "alerts.ntfy_topic", "")
        if topic and "CHANGEME" not in topic:
            notify = lambda msg: send_alert(topic, msg, title="MeSA alert")  # noqa: E731
        else:
            print("[live] alerts.ntfy_topic not set — L2/L3 alerts will only print.")
    engine = build_engine(db, cfg, speak=speak, set_emotion=hub.on_emotion, notify=notify)

    if args.demo:
        _demo(engine, hub)
    elif args.live:
        _live(engine, db, cfg, echo=args.echo)
    else:
        print("Nothing to do. Try: python main.py --demo   or   python main.py --live")
    hub.close()
    db.close()


if __name__ == "__main__":
    main()
