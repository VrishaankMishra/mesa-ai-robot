# Decision-engine soak test results

Run 2026-10-13 · Python 3.14.7 · repo at `11d1244` · `scripts/soak_test.py` (ENG-007)

Command: `PYTHONPATH=. python3 scripts/soak_test.py --hours <H>` (default `--hz 5`)

| Simulated duration | Events processed | Current memory | Peak memory |
| --- | --- | --- | --- |
| 2 h | 36,000 | 12.3 KiB | 12.7 KiB |
| 24 h | 432,000 | 6.4 KiB | 19.1 KiB |
| 168 h (1 week) | 3,024,000 | 9.7 KiB | 19.1 KiB |

Peak memory is flat from 24 h onward: the decision engine processed 3.02 million
events over a simulated week at 5 events/s with no memory growth (tracemalloc peak
19.1 KiB in both the 24 h and 168 h runs). Current memory varies run to run with the
allocator; peak is the leak indicator.

Scope: synthetic events at compressed time — this measures engine state handling,
not camera/microphone drivers. It complements, and does not replace, an on-robot
soak in the home.
