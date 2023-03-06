import json
from urllib.parse import urlparse
from django import http

import requests
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from lemon.activities.objects import as_activitystream
from lemon.models import Person, Note, Activity
from lemon.activities import objects, verbs
from lemon.users.forms import UserRegisterForm
import lemon.users.users_checks as users_checks

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

# вход в систему
def sign_in(request):
    if request.method == 'POST':
        username=request.POST.get("username", "Undefined")
        password=request.POST.get("password", "Undefined")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user=user)
            return HttpResponseRedirect(f"/@{username}")
    return render(request, 'sign-in.html')


def sign_up(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)

        if form.is_valid():
            form.save()
            
            username = form.cleaned_data.get('username')
            name = form.cleaned_data.get('first_name')

            person = Person(username=username, name=name)
            person.save()

            return HttpResponseRedirect(f"/@{person.username}")
        else:
            # TODO: validate mistakes
            print("phhhh....")
        	# messages.success(request, f'Создан аккаунт {username}!')
    else:
        form = UserRegisterForm()
    return render(request, 'sign-up.html', {'form': form})


# главная страница пользователя
@login_required(login_url="/")
def person_main(request, username):
    permission = users_checks.is_visitor(request.user, username)

    person = get_object_or_404(Person, username=username)
    user = get_object_or_404(Person, username=request.user)

    if "get_json" in request.GET:
        return JsonResponse(objects.Actor(person).to_json(context=True))

    collection = objects.OrderedCollection(
        person.notes.all(),
        id=person.uris.notes
    ).items

    data = {"person": person, "user": user, "notes": collection, "permission": permission}
    return render(request, "person-main.html", context=data)


# $ curl -X POST 'http://alice.local/@alice/outbox' -H "Content-Type: application/activity+json"
# -d '{"type": "Follow", "object": "http://bob.local/@bob"}'
@login_required(login_url="/")
def following_view(request, username):
    if users_checks.is_visitor(request.user, username=username):
        return users_checks.response_error()

    user = get_object_or_404(Person, username=username)
    following = objects.OrderedCollection(user.following.all()).items
    # return JsonResponse(following.to_json(context=True))
    return render(request, "following.html", context={"user":user, "following": following})


def following_action(request, username):
    person = get_object_or_404(Person, username=username)

    # TODO: add follow for another server (check)
    username_to = request.POST.get("username", "Undefined")
    instance = request.POST.get("instance", "Undefined")

    if instance != "":
        str_path = "http://{domain}/@{path}".format(domain=instance, path=username_to)
        follow = verbs.Follow(object=str_path)
    else:
        person_to = get_object_or_404(Person, username=username_to)
        follow = verbs.Follow(object=person_to.uris.id)

    requests.post(person.uris.outbox, json=follow.to_json())
    return HttpResponseRedirect(f"/@{person.username}/following")


@login_required(login_url="/")
def followers_view(request, username):
    if users_checks.is_visitor(request.user, username=username):
        return users_checks.response_error()

    user = get_object_or_404(Person, username=username)
    user_followers = user.followers.all()

    # if request.method == "POST":
    #     search = request.POST.get("search", "Undefined")
    #     person_followers = filter(lambda x: search in x["name"] or search in x["preferredUsername"], person_followers)
    #     return render(request, "followers.html", context={"person":person, "followers": person_followers, "search": search})

    if "get_json" in request.GET:
        followers = objects.OrderedCollection(user_followers)
        return JsonResponse(followers.to_json(context=True))
    else:
        user_followers = list(map(lambda x: x.to_activitystream(), user_followers))
        return render(request, "followers.html", context={"user":user, "followers": user_followers, "search": ""})


@csrf_exempt
@login_required(login_url="/")
def outbox_view(request, username):
    person = get_object_or_404(Person, username=username)

    if request.method == "GET":
        user = get_object_or_404(Person, username=request.user)
        if users_checks.is_visitor(request.user, username=username):
            return users_checks.response_error()
        
        _object = user.activities.filter(remote=False).order_by('-created_at')
        collection = objects.OrderedCollection(_object).items
        data = {"user": user, "collection": collection}
        return render(request, "outbox.html", context=data)
        # return JsonResponse(collection.to_json(context=True))

    # создаем активность через тело запроса
    payload = request.body.decode("utf-8")
    activity = json.loads(payload, object_hook=objects.as_activitystream)

    # если активити - сообщение, то оборачиваем в Создать
    if activity.type == "Note":
        obj = activity
        activity = verbs.Create(
            to=person.uris.followers,
            actor=person.uris.id,
            object=obj
        )

    activity.validate()

    if activity.type == "Create":
        if activity.object.type != "Note":
            raise Exception("Sorry, you can only create Notes objects")

        content = activity.object.content

        # сохраняем в БД
        note = Note(content=content, person=person)
        note.save()

        # TODO: check for actor being the right actor object
        activity.object.id = note.uris.id
        activity.id = store(activity, person)
        deliver(activity)

        return HttpResponseRedirect(note.uris.id)

    if activity.type == "Follow":
        # if activity.object.type != "Person":
        #     raise Exception("Sorry, you can only follow Persons objects")

        followed = get_or_create_remote_person(activity.object)
        person.following.add(followed)

        activity.actor = person.uris.id
        activity.to = followed.uris.id
        activity.id = store(activity, person)
        deliver(activity)
        return HttpResponse() # TODO: code 202

    raise Exception("Invalid Request")


def store(activity, person, remote=False):
    payload = bytes(json.dumps(activity.to_json()), "utf-8")
    obj = Activity(payload=payload, person=person, remote=remote)
    if remote:
        obj.ap_id = activity.id
    obj.save()
    return obj.ap_id


def get_or_create_remote_person(ap_id):
    try:
        person = Person.objects.get(ap_id=ap_id)
    except Person.DoesNotExist:
        person   = dereference(ap_id)
        hostname = urlparse(person.id).hostname
        username = "{0}@{1}".format(person.preferredUsername, hostname)
        person = Person(
            username=username,
            name=person.name,
            ap_id=person.id,
            remote=True,
        )
        person.save()
    return person


def deliver(activity):
    audience = activity.get_audience()
    activity = activity.strip_audience()
    audience = get_final_audience(audience)
    for ap_id in audience:
        print(ap_id)
        deliver_to(ap_id, activity)


def get_final_audience(audience):
    final_audience = []
    for ap_id in audience:
        obj = dereference(ap_id)
        if isinstance(obj, objects.Collection):
            final_audience += [item.id for item in obj.items]
        elif isinstance(obj, objects.Actor):
            final_audience.append(obj.id)
        # elif isinstance(obj, objects.Person):
    return set(final_audience)


def deliver_to(ap_id, activity):
    obj = dereference(ap_id)
    if not getattr(obj, "inbox", None):
        return

    res = requests.post(obj.inbox, json=activity.to_json(context=True))
    if res.status_code != 200:
        msg = "Failed to deliver activity {0} to {1}"
        msg = msg.format(activity.type, obj.inbox)
        raise Exception(msg)


def dereference(ap_id, type=None):
    res = requests.get(ap_id, params={"get_json": "true"})

    if res.status_code != 200:
        raise Exception("Failed to dereference {0}".format(ap_id))

    return json.loads(res.text, object_hook=as_activitystream)


@login_required(login_url="/")
def activity(request, username, aid):
    if users_checks.is_visitor(request.user, username=username):
        return users_checks.response_error()
    
    user = get_object_or_404(Person, username=username)
    activity = get_object_or_404(Activity, pk=aid)
    payload = activity.payload.decode("utf-8")
    activity = json.loads(payload, object_hook=objects.as_activitystream)
    # print(activity.type)
    # <Create: {"type": "Create", "to": ["http://bob.local/@bob_the_first"], 
    #           "actor": "http://alice.local/@Alice", 
    #           "object": {"type": "Note", "id": "http://alice.local/@Alice/notes/11", 
    #                      "content": "Test #1. Send message to bob_the_first"}}>
    return render(request, "outbox_item.html", context={"user":user, "activity":activity})
    
    # return JsonResponse(activity.to_json(context=True))


@csrf_exempt
@login_required(login_url="/")
def inbox_view(request, username):
    # http://alice.local/@Alice/inbox/?host=bob.local&actor=@huston&id=10
    person = get_object_or_404(Person, username=username)

    if request.method == "GET":
        if users_checks.is_visitor(request.user, username=username):
            return users_checks.response_error()
    
        hostname = request.GET.get("host", "undefined")
        domen = request.GET.get("domen", "undefined")
        actor = request.GET.get("actor", "undefined")
        _id = request.GET.get("id", -1)

        if hostname != "undefined" and actor != "undefined" and _id != -1 and domen != "undefined":
            ap_id = "http://" + hostname + "." + domen + "/" + actor + "/outbox/" + _id
            print(ap_id)
            activity = Activity.objects.get(ap_id=ap_id)
            
            payload = activity.payload.decode("utf-8")
            activity = json.loads(payload, object_hook=objects.as_activitystream)
            return JsonResponse(activity.to_json(context=True))
            # return render(request, "note_view.html", context=data)

        _object = person.activities.filter(remote=True).order_by('-created_at')
        collection = objects.OrderedCollection(_object).items

        data = {"user": person, "collection": collection}
        return render(request, "inbox.html", context=data)
        # return JsonResponse(collection.to_json(context=True))

    payload = request.body.decode("utf-8")
    activity = json.loads(payload, object_hook=as_activitystream)
    activity.validate()

    if activity.type == "Create":
        handle_note(activity)
    elif activity.type == "Follow":
        handle_follow(activity)

    store(activity, person, remote=True)
    return HttpResponse(f"<h2>Inbox</h2>")


# def inbox_item(request, username, aid):
#     return HttpResponse(f"<p>aid</p>")

def handle_note(activity):
    if isinstance(activity.actor, objects.Actor):
        ap_id = activity.actor.id
    elif isinstance(activity.actor, str):
        ap_id = activity.actor

    person = get_or_create_remote_person(ap_id)

    try:
        note = Note.objects.get(ap_id=activity.object.id)
    except Note.DoesNotExist:
        note = None
    if note:
        return

    note = Note(
        content=activity.object.content,
        person=person,
        ap_id=activity.object.id,
        remote=True
    )

    note.save()
    print(objects.Note(note))

def handle_follow(activity):
    followed = get_object_or_404(Person, ap_id=activity.object)

    if isinstance(activity.actor, objects.Actor):
        ap_id = activity.actor.id
    elif isinstance(activity.actor, str):
        ap_id = activity.actor

    follower = get_or_create_remote_person(ap_id)
    followed.followers.add(follower)


def notes_view(request, username):
    person = get_object_or_404(Person, username=username)
    print("notes-view")
    # <QuerySet [<Note: Note object (1)>, <Note: Note object (3)>, <Note: Note object (4)>]>
    # collection = objects.OrderedCollection(person.notes.all())
    print(person.notes.all())
    collection = objects.OrderedCollection(
        person.notes.all(),
        id=person.uris.notes
    ).items
    data = {"user": person, "notes": collection}
    return render(request, "person-main.html", context=data)
    #return JsonResponse(collection.to_json(context=True))


@login_required(login_url="/")
def note_view(request, username, note_id):
    note = get_object_or_404(Note, pk=note_id)
    return JsonResponse(objects.Note(note).to_json(context=True))


@login_required(login_url="/")
def note_create(request, username):
    person = get_object_or_404(Person, username=username)
    return render(request, "note_create.html")


# curl -X POST 'http://bob.local/@bob/outbox' -H
# "Content-Type: application/activity+json" -d '{"type": "Note", "content": "Good morning!"}'

# POST /@alice/outbox HTTP/1.1
# Host: social.example.com
# Content-Type: application/activity+json
#
# {
#   "type": "Note",
#   "content": "Hello world!"
# }
def note_create_validator(request, username):
    person = get_object_or_404(Person, username=username)

    # TODO: for all followers
    recievers = request.POST.getlist("reciever", ["python"])
    content = request.POST.get("content", "Undefined")

    audience = []
    for reciever in recievers:
        # person1 = get_object_or_404(Person, username=reciever)
        try:
            print(reciever)
            person1 = Person.objects.get(username=reciever)
            audience.append(person1.uris.id)
        except ObjectDoesNotExist:
            continue
            # print("Объект не сушествует")
        except MultipleObjectsReturned:
            continue
            # print("Найдено более одного объекта")
        
    note = objects.Note(content=content)
    create = verbs.Create(to=audience, object=note, actor=person.uris.id)
    requests.post(person.uris.outbox, json=create.to_json())

    # return HttpResponse(f"""
    #             <div>{audience}</div>
    #         """)
    # username1 = request.POST.get("username", "Undefined")
    # content = request.POST.get("content", "Undefined")

    # if username1 == '':
    #     note = objects.Note(content=content)
    #     requests.post(person.uris.outbox, json=note.to_json())
    # else:
    
    return HttpResponseRedirect(f"{person.uris.notes}")

def logout_view(request):
    logout(request)
    return HttpResponseRedirect("/")
