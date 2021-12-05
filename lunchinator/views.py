from django.http import HttpResponse
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import json
from lunchinator.commands import Commands
from lunchinator.text_commands import TextCommands
from slack_api.sender import SlackSender
from lunchinator.models import Restaurant, User
from lunchinator import SlackUser
import itertools
from typing import List, Tuple


sender = SlackSender()
cmd = Commands(sender)
tcmd = TextCommands(sender)


@csrf_exempt
def endpoint(request: HttpRequest):
    action = json.loads(request.POST["payload"])
    type = action["type"]
    user = SlackUser(action["user"]["id"], action["user"]["name"])
    # action_ts = action["action_ts"]
    # message_ts = action["message_ts"]
    # response_url = action["response_url"]

    if type == "block_actions":
        trigger_id = action["trigger_id"]
        actions = action["actions"]

        for action in actions:
            action_id = action["action_id"]

            if action_id == "recommend":
                cmd.recommend_meals(user, 5)
            elif action_id == "restaurants":
                cmd.list_restaurants(user)
            elif action_id == "invite_dialog":
                sender.invite_dialog(trigger_id)
            elif action_id == "print_selection":
                cmd.print_selection(user)
            elif action_id == "quit":
                cmd.quit(user)

            elif action_id.startswith("remove_restaurant"):
                cmd.erase_restaurant(user, action["value"])
            elif action_id.startswith("add_restaurant"):
                cmd.select_restaurant(user, action["value"])
            elif action_id.startswith("select_meal"):
                cmd.select_meal(user, action["value"], recommended=False)
            elif action_id.startswith("select_recommended_meal"):
                cmd.select_meal(user, action["value"], recommended=True)
            elif action_id.startswith("remove_meal"):
                cmd.erase_meal(user, action["value"], recommended=False)
            elif action_id.startswith("remove_recommended_meal"):
                cmd.erase_meal(user, action["value"], recommended=True)

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
    user = SlackUser(request.POST["user_id"], request.POST["user_name"])
    command = request.POST["command"]
    text = request.POST["text"]
    response_url = request.POST["response_url"]

    if command == "/lunch":
        resp = tcmd.lunch_cmd(user, text, response_url)

    elif command == "/lunchrest":
        resp = tcmd.lunch_rest_cmd(user, text)

    else:
        print(f"unsupported slash command: {command}, user = {user}, text = {text}")
        return HttpResponse(status=400)

    if isinstance(resp, HttpResponse):
        return resp
    else:
        return HttpResponse(json.dumps(resp), content_type="application/json")


@csrf_exempt
def trigger(request: HttpRequest):
    if 'restaurant' in request.GET:
        restaurant = request.GET['restaurant']
        resp = cmd.parse_and_send_meals_for_restaurant(restaurant)
        return HttpResponse(bytes(resp, encoding='utf8'))

    cmd.parse_and_send_meals()
    return HttpResponse()


def dashboard(request: HttpRequest):
    selections = Commands.today_selections()
    restaurant_users = [(s.meal.restaurant.name, s.user) for s in selections if s.meal.restaurant.name != Restaurant.ADHOC_NAME]
    adhoc_meal_users = [(s.meal.name, s.user) for s in selections if s.meal.restaurant.name == Restaurant.ADHOC_NAME]

    def group(name_user_list: List[Tuple[str, User]]):
        name_users_grouped = [
            (name, {name_user[1] for name_user in name_users})
            for name, name_users in itertools.groupby(sorted(name_user_list, key=lambda y: y[0]), lambda y: y[0])
        ]
        return [{'name': name, 'users': users}
            for name, users in
            sorted(name_users_grouped, key=lambda name_users: (-len(name_users[1]), name_users[0]))
        ]

    context = {
        'selections': group(restaurant_users) + group(adhoc_meal_users),
    }
    return render(request, 'dashboard.html', context=context)
