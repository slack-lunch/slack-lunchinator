from dataclasses import dataclass


@dataclass
class SlackUser:
    user_id: str
    name: str
