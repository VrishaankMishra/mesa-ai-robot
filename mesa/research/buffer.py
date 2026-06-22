"""Rolling pre-event feature buffer (RES-001).

A time-bounded ring buffer of :class:`~mesa.research.features.FrameFeature`. The vision
loop pushes one frame's features each tick; the buffer keeps only the last
``buffer_seconds`` worth. When the compliance tracker fires a ``taken`` event, the decision
engine reads :meth:`window` and writes it out as one labeled pre-event clip.

Time is taken from each frame's ``ts`` (no wall-clock calls here), so it is fully testable
with synthetic timestamps. See ``docs/research-dataset-design.md`` §6–§7.
"""

from __future__ import annotations

from collections import deque

from mesa.research.features import FrameFeature


class FeatureRingBuffer:
    """Keeps frames whose timestamps fall within ``buffer_seconds`` of the newest frame.

    ``buffer_seconds`` defaults to 6 (the locked decision: store more than the max sweep
    window so the prediction window ``N`` can be chosen offline without recapture).
    """

    def __init__(self, buffer_seconds: float = 6.0):
        if buffer_seconds <= 0:
            raise ValueError("buffer_seconds must be positive")
        self.buffer_seconds = buffer_seconds
        self._frames: deque[FrameFeature] = deque()

    def append(self, frame: FrameFeature) -> None:
        """Add a frame and evict anything older than ``buffer_seconds`` behind it.

        Out-of-order frames (ts older than the current newest) are rejected to keep the
        buffer monotonic — the capture loop produces frames in order.
        """
        if self._frames and frame.ts < self._frames[-1].ts:
            raise ValueError("frame timestamps must be non-decreasing")
        self._frames.append(frame)
        self._evict(frame.ts)

    def _evict(self, newest_ts: float) -> None:
        cutoff = newest_ts - self.buffer_seconds
        while self._frames and self._frames[0].ts < cutoff:
            self._frames.popleft()

    def window(self) -> list[FrameFeature]:
        """Return the buffered frames (oldest first). A snapshot — safe to write out."""
        return list(self._frames)

    def duration(self) -> float:
        """Seconds spanned by the current buffer (0 if fewer than two frames)."""
        if len(self._frames) < 2:
            return 0.0
        return self._frames[-1].ts - self._frames[0].ts

    def clear(self) -> None:
        self._frames.clear()

    def __len__(self) -> int:
        return len(self._frames)
