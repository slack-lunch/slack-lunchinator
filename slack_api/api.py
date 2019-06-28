import os
import slack
from slack_api.singleton import Singleton


class SlackApi(metaclass=Singleton):
    """
    Lowlevel API wrapping Slack API.
    TODO: somehow add content_type = 'application/json; charset=utf-8'
    """

    def __init__(self):
        self._user_channels = {}
        self._client = lambda: slack.WebClient(token=os.environ['LUNCHINATOR_TOKEN'])

    def message(self, channel: str, text: str, blocks: list = None) -> str:
        response = self._client().chat_postMessage(text=SlackApi._encode(text), channel=channel, blocks=blocks)
        assert response["ok"]
        return response["ts"]

    def update_message(self, channel: str, ts: str, text: str, blocks: list = None) -> str:
        try:
            response = self._client().chat_update(text=SlackApi._encode(text), channel=channel, blocks=blocks, ts=ts)
            assert response["ok"]
            return ts
        except:
            print(f"Failed to update message {ts} for {channel}, sending as new")
            return self.message(channel, text, blocks)

    def delete_message(self, channel: str, ts: str):
        try:
            response = self._client().chat_delete(channel=channel, ts=ts)
            assert response["ok"]
        except:
            print(f"Failed to delete message {ts} for {channel}")

    def user_dialog(self, trigger_id: str):
        self._client().dialog_open(dialog={
            "callback_id": "user_selection",
            "title": "Select user",
            "submit_label": "Select",
            "elements": [{
                "type": "select",
                "label": "User",
                "name": "user",
                "data_source": "users"
            }]}, trigger_id=trigger_id)

    def user_channel(self, userid: str) -> str:
        if userid in self._user_channels:
            return self._user_channels[userid]
        else:
            response = self._client().im_open(user=userid)
            assert response["ok"]
            self._user_channels[userid] = response["channel"]["id"]
            return response["channel"]["id"]

    @staticmethod
    def _encode(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
