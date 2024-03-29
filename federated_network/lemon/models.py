import json

from django.db.models import Model, ForeignKey, CharField, TextField, BooleanField, IntegerField
from django.db.models import BinaryField, DateField, ManyToManyField, DateTimeField
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User

from django.conf import settings
from django.urls import reverse


def uri(name, *args):
    domain = settings.FEDERATED_NETWORK_DOMAIN
    path = reverse(name, args=args)
    return "http://{domain}{path}".format(domain=domain, path=path)


class URIs(object):
    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)


class Person(Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)

    ap_id = TextField(null=True)
    remote = BooleanField(default=False)

    online = IntegerField(default=0)

    username = CharField(max_length=100)
    name = CharField(max_length=100)
    following = ManyToManyField('self', symmetrical=False, related_name='followers')

    @property
    def uris(self):
        if self.remote:
            return URIs(id=self.ap_id)

        return URIs(
            id=uri("person", self.username),
            following=uri("following", self.username),
            followers=uri("followers", self.username),
            outbox=uri("outbox", self.username),
            inbox=uri("inbox", self.username),
            notes=uri("notes", self.username),
            liked=uri("liked", self.username)
        )

    def to_activitystream(self):
        json_format = {
            "type": "Person",
            "id": self.uris.id,
            "name": self.name,
            "preferredUsername": self.username,
        }

        if not self.remote:
            json_format.update({
                "following": self.uris.following,
                "followers": self.uris.followers,
                "outbox": self.uris.outbox,
                "inbox": self.uris.inbox,
                "liked": self.uris.liked
            })

        return json_format


class Note(Model):
    ap_id = TextField(null=True)
    remote = BooleanField(default=False)

    person = ForeignKey(Person, related_name='notes', on_delete=models.CASCADE)
    content = CharField(max_length=500)
    likes = ManyToManyField(Person, related_name='liked')

    @property
    def uris(self):
        if self.remote:
            ap_id = self.ap_id
        else:
            ap_id = uri("note", self.person.username, self.id)
        return URIs(id=ap_id)

    def to_activitystream(self):
        return {
            "type": "Note",
            "id": self.uris.id,
            "content": self.content,
            "actor": self.person.uris.id,
        }


class Activity(Model):

    ap_id = TextField()
    payload = BinaryField()
    created_at = DateTimeField(auto_now_add=True)
    person = ForeignKey(Person, related_name='activities', on_delete=models.CASCADE)
    remote = BooleanField(default=False)
    is_read = BooleanField(default=False)

    @property
    def uris(self):
        if self.remote:
            ap_id = self.ap_id
        else:
            ap_id = uri("activity", self.person.username, self.id)
        return URIs(id=ap_id)

    def to_activitystream(self):
        payload = self.payload.decode("utf-8")
        data = json.loads(payload)
        data.update({
            "id": self.uris.id,
            "is_read": self.is_read
        })
        return data


@receiver(post_save, sender=Person)
@receiver(post_save, sender=Note)
@receiver(post_save, sender=Activity)
def save_ap_id(sender, instance, created, **kwargs):
    if created and not instance.remote:
        instance.ap_id = instance.uris.id
        instance.save()


@receiver(post_save, sender=User)
def save_person(sender, instance, created, **kwargs):
    if created:
        Person.objects.create(user=instance, username=instance.username, name=instance.first_name)