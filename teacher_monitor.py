import asyncio
from typing import Optional

from videosdk import Meeting, Participant

TEACHER_ID_SUFFIXES = ("_3", "_5")
ABSENCE_TIMEOUT_SECONDS = 1 * 60


def _is_teacher(participant_id: Optional[str]) -> bool:
    return bool(participant_id) and participant_id.endswith(TEACHER_ID_SUFFIXES)


class TeacherMonitor:
    """Ends the meeting if no 'teacher' participant is present for 10 minutes."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._meeting: Optional[Meeting] = None
        self._teacher_ids: set[str] = set()
        self._timer_handle: Optional[asyncio.TimerHandle] = None
        self._teacher_ever_joined = False

    def attach(self, meeting: Meeting) -> None:
        self._meeting = meeting

    def on_participant_joined(self, participant: Participant) -> None:
        if not _is_teacher(participant.id):
            return
        print(f"[TeacherMonitor] Teacher joined: {participant.display_name} ({participant.id})")
        self._teacher_ids.add(participant.id)
        self._teacher_ever_joined = True
        self._cancel_timer("teacher is in the meeting")

    def on_participant_left(self, participant: Participant) -> None:
        participant_id = getattr(participant, "id", None)
        if not _is_teacher(participant_id):
            return
        self._teacher_ids.discard(participant_id)
        print(f"[TeacherMonitor] Teacher left: {participant_id}")
        if not self._teacher_ids:
            self._start_timer()

    def _start_timer(self) -> None:
        if self._timer_handle is not None:
            return
        print(
            f"[TeacherMonitor] No teacher present. Ending meeting in "
            f"{ABSENCE_TIMEOUT_SECONDS // 60} minutes unless teacher rejoins."
        )
        self._timer_handle = self._loop.call_later(
            ABSENCE_TIMEOUT_SECONDS, self._end_meeting
        )

    def _cancel_timer(self, reason: str) -> None:
        if self._timer_handle is None:
            return
        self._timer_handle.cancel()
        self._timer_handle = None
        print(f"[TeacherMonitor] End timer cancelled — {reason}.")

    def _end_meeting(self) -> None:
        self._timer_handle = None
        if self._meeting is None:
            print("[TeacherMonitor] No meeting attached; cannot end.")
            return
        print("[TeacherMonitor] Teacher did not return within timeout — ending meeting.")
        self._meeting.end()
