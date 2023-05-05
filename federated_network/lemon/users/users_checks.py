from django.http import HttpResponse, HttpResponseRedirect
from lemon.models import Person, Activity
import lemon.users.outbox_deliver as od
from django.conf import settings

# 0 - Ok
# 1 - visitor friend
# 2 - visitor not friend
# 3 - not known visitor
def is_visitor_main(user, person):
    if user == None:
        return 3
    if person == None:
        return 0
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
            print(note)
            note["likes_cnt"] = likes_cnt
            note["likes_people"] = list(map(lambda x: x.to_activitystream(), likes_people))

            note["created_at"] = activity.created_at.strftime('%Y-%m-%d %H:%M')
            # print(type(activity.created_at))

            payload = activity.to_activitystream()
            payload = payload["to"]
            # print(payload)
            if permission == 0:
                note["to"] = payload
            elif len(payload) != 0:
                if payload[0] != person.uris.followers:
                    continue
            
            collection.append(note)
    return collection


# relationship
# 0 - you
# 1 - visitor friend
# 2 - visitor not friend
# 3 - person is friend
# 4 - not known visitor
def get_users_by_hosts(user):
    dict_persons = {}

    for host in settings.ALLOWED_HOSTS:
        dict_persons[host] = []
        
    persons = Person.objects.all()

    for person in persons:
        
        if user != None:
            if user.ap_id == person.ap_id:
                relationship = 0
            else:
                try:
                    user.following.get(ap_id=person.ap_id)
                    relationship  = 1
                except Person.DoesNotExist:
                    relationship  = 2

                try:
                    person.following.get(ap_id=user.ap_id)
                    relationship  = relationship * 10 + 3
                except Person.DoesNotExist:
                    pass
        else:
            relationship = 4
        person = person.to_activitystream()
        person["relationship"] = relationship
        dict_persons[person["id"][7:person["id"].index("@") - 1]].append(person)
    print(dict_persons)
    return dict_persons
