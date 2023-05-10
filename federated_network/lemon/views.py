import json

import requests
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.utils import timezone
import time
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from lemon.activities.objects import as_activitystream
from lemon.models import Person, Note, Activity, uri
from lemon.activities import objects, verbs
from lemon.users.forms import UserRegisterForm
import lemon.users.users_checks as users_checks
import lemon.users.outbox_deliver as outbox_deliver

from django.contrib.auth import authenticate, login, logout


# вход в систему
def sign_in(request):
    data = {}
    if request.method == 'POST':
        username=request.POST.get("username", "Undefined")
        password=request.POST.get("password", "Undefined")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user=user)
            return HttpResponseRedirect(f"/@{username}")
        else:
            data = {"error": "Wrong username or password"}
    return render(request, 'sign-in.html', context=data)


def sign_up(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)

        if form.is_valid():
            form.save(commit=True)
            
            username = form.cleaned_data.get('username')
            # name = form.cleaned_data.get('first_name')

            # person = Person(username=username, name=name)
            # person.save()

            user = authenticate(request, username=username, password=form.cleaned_data.get('password1'))
            if user is not None:
                login(request, user=user)
                return HttpResponseRedirect(uri("person", username))
    else:
        form = UserRegisterForm()
    return render(request, 'sign-up.html', {'form': form})


def about(request):
    if not request.user.is_authenticated:
        user = None
    else:
        user = get_object_or_404(Person, username=request.user)
    
    permission = users_checks.is_visitor_main(user, None)
    data = {"user": user, "permission": permission, "hosts": users_checks.get_users_by_hosts(user)}
    return render(request, "about.html", context=data)


# главная страница пользователя
# @login_required(login_url="/")
def person_main(request, username):
    person = get_object_or_404(Person, username=username)
    
    if "get_json" in request.GET:
        return JsonResponse(objects.Actor(person).to_json(context=True))

    if not request.user.is_authenticated:
        user = None
    else:
        user = get_object_or_404(Person, username=request.user)
        # return HttpResponseRedirect("/")

    permission = users_checks.is_visitor_main(user, person)
    # collection = users_checks.person_get_notes(person)
    collection = users_checks.person_get_all_notes(person, permission)
    print(collection)

    data = {"person": person, "user": user, "notes": collection, "permission": permission}
    return render(request, "person-main.html", context=data)


# $ curl -X POST 'http://alice.local/@alice/outbox' -H "Content-Type: application/activity+json"
# -d '{"type": "Follow", "object": "http://bob.local/@bob"}'
# @login_required(login_url="/")
def following_view(request, username):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
    
    if users_checks.is_visitor(request.user, username=username):
        return users_checks.response_error()

    user = get_object_or_404(Person, username=username)
    # following = objects.OrderedCollection(user.following.all()).items
    following = user.following.all()
    following = list(map(lambda x: x.to_activitystream(), following))

    # create_like()
    # return JsonResponse(following.to_json(context=True))
    return render(request, "following.html", context={"user":user, "following": following})


def liked_view(request, username):
    user = get_object_or_404(Person, username=username)
    following = objects.OrderedCollection(user.following.all()).items
    return JsonResponse(following.to_json(context=True))


def likepost(request):
    if request.method == 'GET':
        person = get_object_or_404(Person, username=request.user)

        activity_id = request.GET['post_id']
        activity = get_object_or_404(Activity, ap_id=activity_id, person=person)

        note = outbox_deliver.get_note_by_activity(activity)

        to = activity.to_activitystream()["actor"]

        like = verbs.Like( 
                      to=[to], 
                      actor=person.ap_id, 
                      object=note.ap_id)

        print(like.to_json())
        response = requests.post(person.uris.outbox, json=like.to_json())
        return HttpResponse(response)


def undo_likepost(request):
    if request.method == 'GET':
        person = get_object_or_404(Person, username=request.user)

        activity_id = request.GET['post_id']
        activity = get_object_or_404(Activity, ap_id=activity_id, person=person)

        note = outbox_deliver.get_note_by_activity(activity)
        
        like_activity = outbox_deliver.get_like_activity_by_person(person, note)
        undo = verbs.Undo(actor=person.ap_id, 
                            object=like_activity.ap_id)
        print(undo.to_json())
        response = requests.post(person.uris.outbox, json=undo.to_json())
        return HttpResponse(response)

# {
#   "@context": "https://www.w3.org/ns/activitystreams",
#   "summary": "Sally deleted a note",
#   "type": "Delete",
#   "actor": {
#     "type": "Person",
#     "name": "Sally"
#   },
#   "object": "http://example.org/notes/1",
#   "origin": {
#     "type": "Collection",
#     "name": "Sally's Notes"
#   }
# }
#     {"@context": "https://www.w3.org/ns/activitystreams",
#  "type": "Like",
#  "id": "https://social.example/alyssa/posts/5312e10e-5110-42e5-a09b-934882b3ecec",
#  "to": ["https://chatty.example/ben/"],
#  "actor": "https://social.example/alyssa/",
#  "object": "https://chatty.example/ben/p/51086"}


def following_action(request):
    if request.method == 'GET':
        user = get_object_or_404(Person, username=request.user)

        if 'followed_id' in request.GET:
            follow = verbs.Follow(object=request.GET['followed_id'])
        elif 'followed_username' in request.GET:
            followed = get_object_or_404(Person, username=request.GET['followed_username'])
            follow = verbs.Follow(object=followed.uris.id)
        else:
            pass
        # print(follow.to_json())
        # print(followed.ap_id)
        response = requests.post(user.uris.outbox, json=follow.to_json())
        return HttpResponse(response)
    return HttpResponse()


# def following_action(request, username):
#     person = get_object_or_404(Person, username=username)

#     # TODO: add follow for another server (check)
#     username_to = request.POST.get("username", "Undefined")
#     instance = request.POST.get("instance", "Undefined")

#     if instance != "":
#         str_path = "http://{domain}/@{path}".format(domain=instance, path=username_to)
#         follow = verbs.Follow(object=str_path)
#     else:
#         person_to = get_object_or_404(Person, username=username_to)
#         follow = verbs.Follow(object=person_to.uris.id)

#     requests.post(person.uris.outbox, json=follow.to_json())
#     return HttpResponseRedirect(f"/@{person.username}/following")


# @login_required(login_url="/")
def followers_view(request, username):
    
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
        if not request.user.is_authenticated:
            return HttpResponseRedirect("/")
    
        if users_checks.is_visitor(request.user, username=username):
            return users_checks.response_error()
        
        user_followers = list(map(lambda x: x.to_activitystream(), user_followers))
        print(user_followers)
        return render(request, "followers.html", context={"user":user, "followers": user_followers, "search": ""})


# @login_required(login_url="/")
@csrf_exempt
def outbox_view(request, username):
    person = get_object_or_404(Person, username=username)

    if request.method == "GET":
        if not request.user.is_authenticated:
            return HttpResponseRedirect("/")
    
        if users_checks.is_visitor(request.user, username=username):
            return users_checks.response_error()
        
        user = get_object_or_404(Person, username=request.user)
        
        _object = user.activities.filter(remote=False).order_by('-id')

        collection = objects.OrderedCollection(_object).to_json(context=True)["orderedItems"]
        # collection = list(map(lambda x: x.to_json(), collection))
        
        data = {"user": user, "collection": collection}
        return render(request, "outbox.html", context=data)
        # return JsonResponse(collection.to_json(context=True))

    # создаем активность через тело запроса
    payload = request.body.decode("utf-8")
    activity = json.loads(payload, object_hook=objects.as_activitystream)

    # если активити - сообщение, то оборачиваем в Создать
    if activity.type == "Note":
        print("In note body")
        obj = activity
        activity = verbs.Create(
            to=person.uris.followers,
            actor=person.uris.id,
            object=obj
        )

    activity.validate()

    if activity.type == "Create":
        print("In create body")
        if activity.object.type != "Note":
            raise Exception("Sorry, you can only create Notes objects")

        content = activity.object.content

        # сохраняем в БД
        note = Note(content=content, person=person)
        note.save()

        # TODO: check for actor being the right actor object
        activity.object.id = note.uris.id
        activity.id = outbox_deliver.store(activity, person)
        outbox_deliver.deliver(activity)

        return HttpResponseRedirect(note.uris.id)
    
    if activity.type == "Undo":
        print("In undo body")

        object_activity = get_object_or_404(Activity, ap_id=activity.object, person=person).to_activitystream()
        if (object_activity["type"] == "Like"):
            liked_note = get_object_or_404(Note, ap_id=object_activity["object"])
            person.liked.remove(liked_note)
            print("remove like")

            activity.actor = person.uris.id
            activity.id = outbox_deliver.store(activity, person)
            activity.to = object_activity["to"]

            print("try to deliver")
            outbox_deliver.deliver(activity)

        return HttpResponse()

    if activity.type == "Follow":
        # if activity.object.type != "Person":
        #     raise Exception("Sorry, you can only follow Persons objects")

        followed = outbox_deliver.get_or_create_remote_person(activity.object)
        person.following.add(followed)

        activity.actor = person.uris.id
        activity.to = followed.uris.id
        activity.id = outbox_deliver.store(activity, person)
        outbox_deliver.deliver(activity)
        return HttpResponse() # TODO: code 202
    
    if activity.type == "Like":
        print("Come to outbox")
        # ------------------------------------------------------------
        # liked = outbox_deliver.get_or_create_remote_person(activity.to[0])
        # ------------------------------------------------------------
        # liked_activity = get_object_or_404(Activity, ap_id=activity.object)
        # print("1. Get activity by activity.object")

        # liked_activity = liked_activity.to_activitystream()["object"]
        # print("2. Get activity.object by to_activity...()")

        liked_note = get_object_or_404(Note, ap_id=activity.object)
        print("3. Get note")
        # get_object_or_404(Note, ap_id=liked_note).likes.add(person)
        person.liked.add(liked_note)
        print("4. Add to liked")

        activity.actor = person.uris.id
        activity.id = outbox_deliver.store(activity, person)
        outbox_deliver.deliver(activity)
        return HttpResponse()

    raise Exception("Invalid Request")


# @login_required(login_url="/")
def activity(request, username, aid):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
    
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

# @login_required(login_url="/")
@csrf_exempt
def inbox_view(request, username):
    # http://alice.local/@Alice/inbox/?host=bob.local&actor=@huston&id=10
    person = get_object_or_404(Person, username=username)

    if request.method == "GET":
        if not request.user.is_authenticated:
            return HttpResponseRedirect("/")
        
        if users_checks.is_visitor(request.user, username=username):
            return users_checks.response_error()
    
        hostname = request.GET.get("host", "undefined")
        domen = request.GET.get("domen", "undefined")
        actor = request.GET.get("actor", "undefined")
        _id = request.GET.get("id", -1)

        if hostname != "undefined" and actor != "undefined" and _id != -1 and domen != "undefined":
            ap_id = "http://" + hostname + "." + domen + "/" + actor + "/outbox/" + _id
            # print(ap_id)
            activity = Activity.objects.get(ap_id=ap_id, person=person)
            liked = outbox_deliver.get_if_like_by_activity(activity)

            payload = activity.payload.decode("utf-8")
            activity = json.loads(payload, object_hook=objects.as_activitystream)

            return render(request, "inbox_item.html", context={"user":person, "activity":activity, "liked": liked})
            # return JsonResponse(activity.to_json(context=True))
            # return render(request, "note_view.html", context=data)

        _object = person.activities.filter(remote=True).order_by('-id')
        collection = objects.OrderedCollection(_object).to_json(context=True)["orderedItems"]

        data = {"user": person, "collection": collection}
        print(data)
        return render(request, "inbox.html", context=data)

    payload = request.body.decode("utf-8")
    activity = json.loads(payload, object_hook=as_activitystream)
    activity.validate()

    if activity.type == "Create":
        handle_note(activity)
    elif activity.type == "Follow":
        handle_follow(activity)
    elif activity.type == "Like":
        handle_like(activity)
    elif activity.type == "Undo":
        print("inbox undo")
        handle_undo(activity, person)

    outbox_deliver.store(activity, person, remote=True)
    return HttpResponse(f"<h2>Inbox</h2>")


# def inbox_item(request, username, aid):
#     return HttpResponse(f"<p>aid</p>")

def handle_note(activity):
    if isinstance(activity.actor, objects.Actor):
        ap_id = activity.actor.id
    elif isinstance(activity.actor, str):
        ap_id = activity.actor

    person = outbox_deliver.get_or_create_remote_person(ap_id)

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

    follower = outbox_deliver.get_or_create_remote_person(ap_id)
    followed.followers.add(follower)


def handle_like(activity):
    # ------------------------------------------------------------
    who_liked = outbox_deliver.get_or_create_remote_person(ap_id = activity.actor)
    # ------------------------------------------------------------
    if isinstance(activity.actor, objects.Actor):
        ap_id = activity.actor.id
    elif isinstance(activity.actor, str):
        ap_id = activity.actor

    # liked_activity = get_object_or_404(Activity, ap_id=activity.object)
    # liked_activity = liked_activity.to_activitystream()["object"]
    # liked_note = liked_activity["id"]
    get_object_or_404(Note, ap_id=activity.object).likes.add(who_liked)

    # activity.actor = person.uris.id
    # activity.id = outbox_deliver.store(activity, person)
    # outbox_deliver.deliver(activity)


def handle_undo(activity, person):
    who_liked = outbox_deliver.get_or_create_remote_person(ap_id = activity.actor)

    if isinstance(activity.actor, objects.Actor):
        ap_id = activity.actor.id
    elif isinstance(activity.actor, str):
        ap_id = activity.actor

    object_activity = get_object_or_404(Activity, ap_id=activity.object, person=person).to_activitystream()
    if (object_activity["type"] == "Like"):
        print("try to remove")
        get_object_or_404(Note, ap_id=object_activity["object"]).likes.remove(who_liked)


def notes_view(request, username):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
    
    person = get_object_or_404(Person, username=username)

    # print("notes-view")
    # <QuerySet [<Note: Note object (1)>, <Note: Note object (3)>, <Note: Note object (4)>]>
    # collection = objects.OrderedCollection(person.notes.all())
    # print(person.notes.all())

    collection = objects.OrderedCollection(
        person.notes.all(),
        id=person.uris.notes
    ).items
    
    data = {"user": person, "notes": collection}
    return render(request, "person-main.html", context=data)
    #return JsonResponse(collection.to_json(context=True))


# @login_required(login_url="/")
def note_view(request, username, note_id):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
    
    note = get_object_or_404(Note, pk=note_id)
    return JsonResponse(objects.Note(note).to_json(context=True))


# @login_required(login_url="/")
def note_create(request, username):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
    
    person = get_object_or_404(Person, username=username)

    to_id = request.GET.get("to", "undefined")
    print(to_id)
    return render(request, "note_create.html", context={"user": person, "to": to_id})


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
    recievers = request.POST.getlist("reciever", [])
    
    # print(request.POST)
    content = request.POST.get("content", "Undefined")

    audience = []
    for reciever in recievers:
        # person1 = get_object_or_404(Person, username=reciever)
        try:
            # print(reciever)
            person1 = Person.objects.get(username=reciever)
            audience.append(person1.uris.id)
        except ObjectDoesNotExist:
            # print("Объект не сушествует")
            continue            
        except MultipleObjectsReturned:
            # print("Найдено более одного объекта")
            continue
    
    if len(audience) == 0:
        audience.append(person.uris.followers)
    
    # print(audience)
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
    
    return HttpResponseRedirect(f"{person.uris.id}")

def logout_view(request):
    logout(request)
    return HttpResponseRedirect("/")


# from datetime import datetime


# @require_GET
# def sse(request):
#     response = StreamingHttpResponse(content_type='text/event-stream')
#     person = get_object_or_404(Person, username=request.user)

#     def stream():
#         # updates = Activity.objects.filter(created_at__gt=datetime(2023, 1, 1, 0, 0, 0))
#         # print(updates)
#         # print("Hello")
#         # yield b"data: Hello\n\n"
#         # time.sleep(1)
#         last_update_time = timezone.now()

#         while True:
#             inserts = person.activities.filter(remote=True, created_at__gt=last_update_time).order_by('-id')
#             print(len(inserts))
#             if len(inserts) > 0:
#                 collection = objects.OrderedCollection(inserts).to_json(context=True)["orderedItems"]
#                 yield f"data: {json.dumps(collection)}\n\n"
#                 last_update_time = inserts.last().created_at
#             time.sleep(10)

#     response.streaming_content = stream()
#     return response