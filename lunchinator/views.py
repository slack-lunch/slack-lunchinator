from django.http import HttpResponse
from django.http import HttpRequest
import json
from lunchinator.commands import Commands


def endpoint(request: HttpRequest):
    action = json.loads(request.POST["payload"])
    type = action["type"]
    userid = action["user"]["id"]
    callback_id = action["callback_id"]
    # trigger_id = action["trigger_id"]
    # action_ts = action["action_ts"]
    # message_ts = action["message_ts"]
    # response_url = action["response_url"]
    actions = action["actions"]

    cmd = Commands()

    # [{'name': 'meal', 'type': 'button', 'value': '4'}]
    # "name": "channels_list", "selected_options": [ { "value": "C012AB3CD"

    if type == "interactive_message":
        if callback_id == "restaurants_selection":
            cmd.select_restaurants(userid, [a["value"] for a in actions if a["name"] == "restaurant"])
        elif callback_id == "meals_selection":
            cmd.select_meals(userid, [a["value"] for a in actions if a["name"] == "meal"], recommended=False)
        elif callback_id == "recommendations_selection":
            cmd.select_meals(userid, [a["value"] for a in actions if a["name"] == "meal"], recommended=True)

        elif callback_id == "other_ops":
            for operation in [a["value"] for a in actions if a["name"] == "operation"]:
                if operation == "erase":
                    cmd.erase(userid)
                elif operation == "recommend":
                    cmd.recommend(userid)
                elif operation == "restaurants":
                    cmd.list_restaurants()
                elif operation == "clear_restaurants":
                    cmd.clear_restaurants(userid)
                else:
                    print("unsupported operation: " + operation)
                    return HttpResponse(status=400)

        else:
            print("unsupported callback id: " + callback_id)
            return HttpResponse(status=400)
        return HttpResponse("ok")
    else:
        print("unsupported request")
        return HttpResponse(status=400)
