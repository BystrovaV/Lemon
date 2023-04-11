from django.http import HttpResponse, HttpResponseRedirect
from lemon.models import Person, Activity
import lemon.users.outbox_deliver as od

# 0 - Ok
# 1 - visitor friend
# 2 - visitor not friend
# 3 - not known visitor
def is_visitor_main(user, person):
    if user == None:
        return 3
    if user.username != person.username:
        try:
            user.following.get(ap_id=person.ap_id)
            return 1
        except Person.DoesNotExist:
            return 2
    return 0


def is_visitor(user, username):
    return str(user.username) != str(username)


def response_error():
    response = HttpResponse()
    response.status_code = 403
    return response

def is_signin(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")


def person_get_notes(person):
    notes = person.notes.all().order_by('-id')
    collection = []
    for note in notes:
        likes_cnt = note.likes.count()
        likes_people = note.likes.all()
        note = note.to_activitystream()
        note["likes_cnt"] = likes_cnt
        note["likes_people"] = list(map(lambda x: x.to_activitystream(), likes_people))
        collection.append(note)
    
    return collection


def person_get_all_notes(person, permission):
    activities = person.activities.filter(remote=False).order_by("-id")

    collection = []
    for activity in activities:
        note = od.get_note_by_activity(activity)
        if note != None:
            likes_cnt = note.likes.count()
            likes_people = note.likes.all()

            note = note.to_activitystream()
            note["likes_cnt"] = likes_cnt
            note["likes_people"] = list(map(lambda x: x.to_activitystream(), likes_people))

            note["created_at"] = activity.created_at

            payload = activity.to_activitystream()
            payload = payload["to"]
            # print(payload)
            if permission == 0:
                note["to"] = payload
            elif len(payload) != 0:
                continue
            
            collection.append(note)
    return collection