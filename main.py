import asyncio
import os

import dotenv
from videosdk import MeetingConfig, VideoSDK

from meeting_events import MyMeetingEventHandler
from teacher_monitor import TeacherMonitor

dotenv.load_dotenv()

VIDEOSDK_TOKEN = os.getenv("VIDEOSDK_TOKEN")
MEETING_ID = os.getenv("MEETING_ID")
NAME = os.getenv("NAME", "Monitor Bot")

loop = asyncio.get_event_loop()


def main():
    teacher_monitor = TeacherMonitor(loop=loop)

    meeting_config = MeetingConfig(
        meeting_id=MEETING_ID,
        name=NAME,
        mic_enabled=False,
        webcam_enabled=False,
        token=VIDEOSDK_TOKEN,
    )

    meeting = VideoSDK.init_meeting(**meeting_config)
    teacher_monitor.attach(meeting)

    meeting.add_event_listener(MyMeetingEventHandler(teacher_monitor=teacher_monitor))

    print("initialized meeting with ID:", meeting.id)
    meeting.join()
    print(
        "joined as",
        meeting.local_participant.id,
        meeting.local_participant.display_name,
    )


if __name__ == "__main__":
    main()
    loop.run_forever()
