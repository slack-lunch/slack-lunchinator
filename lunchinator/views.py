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
    callback_id = action["callback_id"]
    # action_ts = action["action_ts"]
    # message_ts = action["message_ts"]
    # response_url = action["response_url"]
    cmd = Commands()
    sender = SlackSender()

    if type == "interactive_message":
        trigger_id = action["trigger_id"]
        actions = action["actions"]

        if callback_id == "restaurants_selection":
            cmd.select_restaurants(userid, [a["value"] for a in actions if a["name"] == "restaurant"])
        elif callback_id == "meals_selection":
            cmd.select_meals(userid, [a["value"] for a in actions if a["name"] == "meal"], recommended=False)
        elif callback_id == "recommendations_selection":
            cmd.select_meals(userid, [a["value"] for a in actions if a["name"] == "meal"], recommended=True)

        elif callback_id == "other_ops":
            for operation in [a["value"] for a in actions if a["name"] == "operation"]:
                if operation == "erase":
                    cmd.erase_meals(userid)
                elif operation == "recommend":
                    cmd.recommend_meals(userid, 5)
                elif operation == "restaurants":
                    cmd.list_restaurants(userid)
                elif operation == "clear_restaurants":
                    cmd.clear_restaurants(userid)
                elif operation == "invite_dialog":
                    sender.invite_dialog(trigger_id)
                else:
                    print("unsupported operation: " + operation)
                    return HttpResponse(status=400)

        else:
            print("unsupported callback id: " + callback_id)
            return HttpResponse(status=400)

    elif type == "dialog_submission":
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
