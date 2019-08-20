from django.http import HttpResponse
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
import json
from lunchinator.commands import Commands
from slack_api.sender import SlackSender


sender = SlackSender()
cmd = Commands(sender)


@csrf_exempt
def endpoint(request: HttpRequest):
    action = json.loads(request.POST["payload"])
    type = action["type"]
    userid = action["user"]["id"]
    # action_ts = action["action_ts"]
    # message_ts = action["message_ts"]
    # response_url = action["response_url"]

    if type == "block_actions":
        trigger_id = action["trigger_id"]
        actions = action["actions"]

        for action in actions:
            action_id = action["action_id"]

            if action_id == "recommend":
                cmd.recommend_meals(userid, 5)
            elif action_id == "restaurants":
                cmd.list_restaurants(userid)
            elif action_id == "invite_dialog":
                sender.invite_dialog(trigger_id)
            elif action_id == "print_selection":
                cmd.print_selection(userid)
            elif action_id == "quit":
                cmd.quit(userid)

            elif action_id.startswith("remove_restaurant"):
                cmd.erase_restaurants(userid, [action["value"]])
            elif action_id.startswith("add_restaurant"):
                cmd.select_restaurants(userid, [action["value"]])
            elif action_id.startswith("select_meal"):
                cmd.select_meals(userid, [action["value"]], recommended=False)
            elif action_id.startswith("select_recommended_meal"):
                cmd.select_meals(userid, [action["value"]], recommended=True)
            elif action_id.startswith("remove_meal"):
                cmd.erase_meals(userid, [action["value"]])

            else:
                print("unsupported action_id: " + action_id)
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


@csrf_exempt
def slash(request: HttpRequest):
    user_id = request.POST["user_id"]
    command = request.POST["command"]
    text = request.POST["text"]

    if command == "/lunch":
        if not text:
            resp = {
                "response_type": "ephemeral",
                "text": "Welcome to Lunchinator!\n"
                        "* `/lunch` is for voting (`/vote A3,B5`), or recommending (`/vote "
                        "recommend 6`).\n"
                        "* `/lunch erase A2,B7` erases your selection today.\n"
                        "* There is also `/lunchrest` for "
                        "printing (`/lunchrest`) or selecting (`/lunchrest A,B`) your favourite restaurants, "
                        "or clearing them (`/lunchrest erase A,B`). "
            }
            return HttpResponse(json.dumps(resp), content_type="application/json")
        elif text.startswith("recommend"):
            if len(text) > 9:
                try:
                    count = int(text[9:].strip())
                    if count <= 0 or count > 20:
                        raise ValueError("Invalid recommendation count")
                except ValueError:
                    return HttpResponse(
                        json.dumps({"response_type": "ephemeral", "text": "Invalid count to recommend."}),
                        content_type="application/json")
            else:
                count = 5
            cmd.recommend_meals(user_id, count)
        elif text.startswith("erase"):
            cmd.erase_meals_by_text(user_id, text[5:].strip())
        else:
            resp = cmd.select_meals_by_text(user_id, text)
            if resp:
                return HttpResponse(json.dumps(resp), content_type="application/json")

    elif command == "/lunchrest":
        if not text:
            cmd.list_restaurants(user_id)
        elif text == "erase":
            cmd.erase_restaurants_by_text(user_id, text[5:].strip())
        else:
            cmd.select_restaurants_by_text(user_id, text)

    else:
        print(f"unsupported slash command: {command}, user_id = {user_id}, text = {text}")
        return HttpResponse(status=400)

    return HttpResponse()


@csrf_exempt
def trigger(request: HttpRequest):
    cmd.parse_and_send_meals()
    return HttpResponse()
