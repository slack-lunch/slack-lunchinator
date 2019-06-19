import os
import slack

"""
Lowlevel API wrapping Slack API.
TODO: somehow add content_type = 'application/json; charset=utf-8'
"""
class SlackApi:
    __instance = None

    def __new__(cls):
        if SlackApi.__instance is None:
            SlackApi.__instance = object.__new__(cls)
        return SlackApi.__instance

    def __init__(self):
        self._username = "Lunchinator"
        self._user_channels = {}
        self._client = slack.WebClient(token=os.environ['LUNCHINATOR_TOKEN'])

    def message(self, channel: str, text: str, attachments: list = None) -> str:
        response = self._client.chat_postMessage(text=SlackApi._encode(text), channel=channel, attachments=attachments, username=self._username, as_user=False)
        assert response["ok"]
        return response["ts"]

    def update_message(self, channel: str, ts: str, text: str, attachments: list = None):
        print(f"edit {ts} to {channel}: {text}: {attachments}")
        response = self._client.chat_update(text=SlackApi._encode(text), channel=channel, attachments=attachments, username=self._username, as_user=False, ts=ts)
        assert response["ok"]

    def user_channel(self, userid: str) -> str:
        if userid in self._user_channels:
            return self._user_channels[userid]
        else:
            response = self._client.im_open(user=userid)
            assert response["ok"]
            self._user_channels[userid] = response["channel"]["id"]
            return response["channel"]["id"]

    @staticmethod
    def _encode(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
