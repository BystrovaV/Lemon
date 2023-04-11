import json
from urllib.parse import urlparse

import requests
from django.shortcuts import get_object_or_404

from lemon.activities.objects import as_activitystream
from lemon.models import Person, Activity, Note
from lemon.activities import objects


# если активити remote = false,
# автоматически outbox/id = id
# если remote = true
# присваивается ap_id = ap_id (который со стороны remote=false)
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
    print("In deliver")
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
    print("Get Final audience")
    print(final_audience)
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
    print("Success deliver")


def dereference(ap_id, type=None):
    print(ap_id)
    res = requests.get(ap_id, params={"get_json": "true"})

    if res.status_code != 200:
        raise Exception("Failed to dereference {0}".format(ap_id))

    return json.loads(res.text, object_hook=as_activitystream)


def get_if_like_by_activity(activity):
    note = get_note_by_activity(activity=activity)
    if note != None:
        return note.likes.contains(activity.person)
    

def get_note_by_activity(activity):
    payload = activity.to_activitystream()
    if payload["type"] != "Create":
        return
    
    payload = payload["object"]
    if payload["type"] == "Note":
        note_id = payload["id"]
        note = get_object_or_404(Note, ap_id = note_id)
        return note
    return None
    

def get_like_activity_by_person(person, note):
    activities = Activity.objects.all().filter(person=person).order_by("-id")

    for activity in activities:
        activity_stream = activity.to_activitystream()
        if activity_stream["type"] == "Like":
            if activity_stream["object"] == note.ap_id:
                return activity
            