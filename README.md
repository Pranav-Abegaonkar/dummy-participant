# VideoSDK Dummy-Participant Monitor

A small Python script that joins a VideoSDK meeting as a passive
("dummy") participant, watches who's in the room, and ends the meeting
if no teacher is present for 10 minutes.

Use case: a tutoring product that wants to auto-close a classroom when
the tutor disconnects and doesn't return.

## How it works

```
python main.py
     │
     ▼
.env loaded ──► VIDEOSDK_TOKEN, MEETING_ID, NAME
     │
     ▼
VideoSDK.init_meeting(...)  ──►  bot joins as RECV_ONLY (mic/webcam off,
     │                            no media consumed — only signaling)
     ▼
TeacherMonitor wired to the meeting's RoomClient
     │
     ▼
asyncio loop runs forever, handling participant events
```

Once joined, the bot watches three events on the underlying
`RoomClient`:

- **`MEETING_JOINED`** — the join response includes the list of peers
  already in the room. The bot scans this list for any participant whose
  ID ends in `_3` or `_5` (the "teacher" suffix) and adds them to the
  tracked set.
- **`ADD_PEER`** — fires when a new peer joins after the bot. Same
  suffix check; if it's a teacher, add to the tracked set.
- **`REMOVE_PEER`** — fires when any peer leaves. If the leaving peer
  is in the tracked teachers set, remove it.

State machine:

| State | Trigger | Action |
| --- | --- | --- |
| Teacher present | another teacher joins/leaves | nothing — stay idle |
| Teacher present | **last** teacher leaves | start 10-min timer |
| Timer running | a teacher (re)joins | cancel timer |
| Timer running | timer fires | call `meeting.end()` — closes the meeting for everyone |

## File map

| File | Responsibility |
| --- | --- |
| [`main.py`](main.py) | Loads `.env`, builds the `Meeting`, wires `TeacherMonitor`, joins, runs the asyncio loop |
| [`teacher_monitor.py`](teacher_monitor.py) | The presence rule (event handlers + timer) |
| [`requirements.txt`](requirements.txt) | Python dependencies |
| `.env` | Per-run config: token, meeting id, display name |

## Setup

Create a `.env` from the example and fill in your values:

```bash
cp .env.example .env
```

`.env` keys:

| Key | Required | Notes |
| --- | --- | --- |
| `VIDEOSDK_TOKEN` | yes | VideoSDK JWT, must include `allow_join` permission |
| `MEETING_ID` | yes | The VideoSDK meeting ID to join |
| `NAME` | no | Display name for the bot in the meeting (default: `Monitor Bot`) |

Install dependencies (use a venv):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Stop with `Ctrl+C`. The bot will leave the meeting cleanly on shutdown.

## Configuration

The two rule parameters live as module constants at the top of
[`teacher_monitor.py`](teacher_monitor.py):

```python
TEACHER_ID_SUFFIXES = ("_3", "_5")
ABSENCE_TIMEOUT_SECONDS = 10 * 60
```

- `TEACHER_ID_SUFFIXES` — participant IDs ending in any of these are
  treated as teachers. Edit the tuple to match your product's ID format.
- `ABSENCE_TIMEOUT_SECONDS` — how long to wait after the last teacher
  leaves before ending the meeting. Set this to a smaller value (e.g. `60`)
  while testing.

## Logs

What you'll see during normal operation:

```
[INFO] root: initialized meeting p8x7-o3hk-t3hl
[INFO] teacher_monitor: teacher joined: test_3
[INFO] teacher_monitor: teacher left: test_3
[INFO] teacher_monitor: no teacher present. ending meeting in 10 min unless teacher rejoins.
[INFO] teacher_monitor: teacher joined: test_5
[INFO] teacher_monitor: end timer cancelled — teacher rejoined.
[INFO] teacher_monitor: teacher left: test_5
[INFO] teacher_monitor: no teacher present. ending meeting in 10 min unless teacher rejoins.
[WARNING] teacher_monitor: teacher absent past timeout — ending meeting.
```

`aioice`, `vsaiortc`, and `videosdk.room_client` are demoted to
`WARNING` in [`main.py`](main.py) because their INFO output is mostly
ICE/RTP plumbing.

## Test it

In a browser, open the VideoSDK prebuilt URL with a teacher-suffix
participant ID:

```
https://embed.videosdk.live/rtc-js-prebuilt/<version>/?meetingId=<MEETING_ID>&token=<TOKEN>&participantId=test_3&name=teacher
```

Then:

1. Run `python main.py` — bot joins, you see it in the dashboard.
2. The teacher tab is open, you see `teacher already in room: test_3`
   in the bot's logs.
3. Close the teacher's browser tab — you see `teacher left: test_3`
   followed by `no teacher present. ending meeting in 10 min...`
4. Reopen the URL within 10 min → end timer cancelled.
5. Stay closed past 10 min → meeting ends for everyone.

## SDK quirks worked around

Three issues in `videosdk` 0.3.2 that are worth knowing about (and
re-checking on SDK upgrades):

1. **Pre-existing peers aren't replayed as join events.** When the bot
   joins a room with peers already present, the SDK fires
   `MEETING_JOINED` with the peer list bundled in the payload but does
   not iterate through `ADD_PEER`. We work around this by reading the
   existing-peers list out of `MEETING_JOINED` and registering teachers
   from it directly.

2. **Leave events for unknown peers are silently dropped.** The SDK's
   `participant_left` handler at `meeting.py:348` checks
   `if id in self.__participants:` — so for any peer the bot never saw
   join (anyone already in the room when the bot arrived), the leave
   event is dropped on the floor. We avoid this by listening to
   `REMOVE_PEER` directly on `room_client` instead of the high-level
   `participant_left`.

3. **`chat_enabled=False` crashes the join.** The SDK conditionally
   sends `sctpCapabilities` based on the datachannel flag but
   unconditionally reads `sctpParameters` from the response
   (`room_client.py:543`). We therefore set `chat_enabled=True` in
   `main.py` even though we don't use chat. The cost is negligible.

Both #1 and #2 are reached by accessing `meeting._Meeting__room_client`
(Python name-mangled private). Re-check on every SDK upgrade.
