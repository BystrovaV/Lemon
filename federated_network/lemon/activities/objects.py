import json
from django.contrib.sites import requests


class Object(object):
    attributes = ["type", "id", "name", "to", "bto", "bcc", "cc"]
    type = "Object"

    @classmethod
    def from_json(cls, json):
        return Object(**json)

    # Constructor in which kwargs - dictionary of activity
    # They are added in attributes of object
    def __init__(self, obj=None, **kwargs):
        if obj:
            self.__init__(**obj.to_activitystream())

        for key in self.attributes:
            if key == "type":
                continue

            value = kwargs.get(key)
            if value is None:
                continue

            # if isinstance(value, dict) and value.get("type"):
            #     value =
            self.__setattr__(key, value)

    def __str__(self):
        content = json.dumps(self, default=encode_activitystream)
        return "<{type}: {content}>".format(type=self.type, content=content)

    # From object to json
    def to_json(self, context=False):
        values = {}
        for attribute in self.attributes:
            value = getattr(self, attribute, None)
            if value is None:
                continue
            if isinstance(value, Object):
                value = value.to_json()
            # if getattr(value, "__iter__", None):
            #     value = [item.to_json() for item in value]
            values[attribute] = value
        get_from_array(values, "to")
        get_from_array(values, "bto")
        get_from_array(values, "bcc")
        get_from_array(values, "cc")
        # to = values.get("to")
        # if isinstance(to, str):
        #     values["to"] = [to]
        # elif getattr(to, "__iter__", None):
        #     values["to"] = []
        #     for item in to:
        #         if isinstance(item, str):
        #             values["to"].append(item)
        #         if isinstance(item, Object):
        #             values["to"].append(item.id)

        if context:
            values["@context"] = "https://www.w3.org/ns/activitystreams"
        return values

    def to_activitystream(self):
        return self


def get_from_array(values, title):
    arr = values.get(title)
    if isinstance(arr, str):
        values[title] = [arr]
    elif getattr(arr, "__iter__", None):
        values[title] = []
        for item in arr:
            if isinstance(item, str):
                values[title].append(item)
            if isinstance(item, Object):
                values[title].append(item.id)


class Note(Object):
    attributes = Object.attributes + ["content", "actor"]
    type = "Note"


class Actor(Object):
    # inbox - OrderedCollection
    # outbox - OrderedCollection
    # followers - collection
    # following - collection
    attributes = Object.attributes + ["inbox", "outbox", "followers", "following", "preferredUsername"]
    type = "Actor"

    def send(self, activity):
        res = requests.post(self.inbox, json=activity.to_json(context=True))
        if res.status_code != 200:
            raise Exception


class Person(Object):
    type = "Person"


class Collection(Object):
    attributes = Object.attributes + ["items", "totalItems"]
    type = "Collection"

    def __init__(self, iterable=None, **kwargs):
        self._items = []

        Object.__init__(self, **kwargs)
        if iterable is None:
            return

        self.items = iterable

    @property
    def items(self):
        return self._items

    @items.setter
    def items(self, iterable):
        for item in iterable:
            if isinstance(item, Object):
                self._items.append(item)
            elif getattr(item, "to_activitystream", None):
                item = as_activitystream(item.to_activitystream())
                self._items.append(item)
            else:
                raise Exception("invalid ActivityStream object: {item}".format(item=item))

    def to_json(self, **kwargs):
        json = Object.to_json(self, **kwargs)
        items = [item.to_json() if isinstance(item, Object) else item
                 for item in self.items]
        json.update({
            "items": items
        })
        return json


class OrderedCollection(Collection):

    attributes = Object.attributes + ["orderedItems", "totalItems"]
    type = "OrderedCollection"

    @property
    def totalItems(self):
        return len(self.items)

    @totalItems.setter
    def totalItems(self, value):
        pass

    @property
    def orderedItems(self):
        return self.items

    @orderedItems.setter
    def orderedItems(self, iterable):
        self.items = iterable

    def to_json(self, **kwargs):
        json = Collection.to_json(self, **kwargs)
        json["orderedItems"] = json["items"]
        del json["items"]
        return json


def encode_activitystream(obj):
    if isinstance(obj, Object):
        return obj.to_json()


ALLOWED_TYPES = {
    "Object": Object,
    "Actor": Actor,
    "Person": Person,
    "Note": Note,
    "Collection": Collection,
    "OrderedCollection": OrderedCollection
}


def as_activitystream(obj):
    type = obj.get("type")

    if not type:
        msg = "Invalid ActivityStream object, the type is missing"
        raise Exception(msg)

    if type in ALLOWED_TYPES:
        return ALLOWED_TYPES[type](**obj)

    raise Exception("Invalid Type {0}".format(type))
