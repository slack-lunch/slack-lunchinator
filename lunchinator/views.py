from django.http import HttpResponse
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
import json
from lunchinator.commands import Commands
from slack_api.sender import SlackSender


@csrf_exempt
def endpoint(request: HttpRequest):
    action = json.loads(request.POST["payload"])
    type = action["type"]
    userid = action["user"]["id"]
    # action_ts = action["action_ts"]
    # message_ts = action["message_ts"]
    # response_url = action["response_url"]
    cmd = Commands()
    sender = SlackSender()

    if type == "block_actions":
        trigger_id = action["trigger_id"]
        actions = action["actions"]

        for action in actions:
            if action["action_id"] == "erase":
                cmd.erase_meals(userid)
            elif action["action_id"] == "recommend":
                cmd.recommend_meals(userid, 5)
            elif action["action_id"] == "restaurants":
                cmd.list_restaurants(userid)
            elif action["action_id"] == "clear_restaurants":
                cmd.clear_restaurants(userid)
            elif action["action_id"] == "invite_dialog":
                sender.invite_dialog(trigger_id)
            elif action["action_id"] == "print_selection":
                cmd.print_selection(userid)
            elif action["action_id"] == "quit":
                cmd.quit(userid)

            elif action["block_id"].startswith("restaurants"):
                cmd.select_restaurants(userid, [action["value"]])
            elif action["block_id"].startswith("meals"):
                cmd.select_meals(userid, [action["value"]], recommended=False)
            elif action["block_id"].startswith("recommended_meals"):
                cmd.select_meals(userid, [action["value"]], recommended=True)

            else:
                print("unsupported action_id / block_id: " + action["action_id"] + " / " + action["block_id"])
                return HttpResponse(status=400)

    elif type == "dialog_submission":
        callback_id = action["callback_id"]
        submission = action["submission"]

        if callback_id == "user_selection":
            sender.invite(submission["user"])
        else:
            print("unsupported callback id: " + callback_id)
            return HttpResponse(status=400)

    else:
        print("unsupported request")
        return HttpResponse(status=400)

    return HttpResponse()
