import asyncio
from enum import Enum
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

from django.db.models import F
from lemon.activities import objects
from lemon.models import Activity, Person

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_name = self.scope["url_route"]["kwargs"]["user_name"]
        self.user_groop_name = "user_%s" % self.user_name

        user = self.scope["user"]
        
        if user.is_authenticated:
            await self.update_user_incr(self.user_name)

        await self.channel_layer.group_add(self.user_groop_name, self.channel_name)
        await self.send_cnt_msg()

        await self.accept()

    async def disconnect(self, close_code):
        await self.update_user_decr(self.user_name)
        await self.channel_layer.group_discard(self.user_groop_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data["type"] == "is_read":
            await self.update_message_is_read(self.user_name, data["message_id"],
                                               True if data["message"] == "true" else False)

            await self.send_cnt_msg()
            
    async def send_cnt_msg(self):
        cnt_msg = await self.get_cnt_message()
        await self.channel_layer.group_send(
            self.user_groop_name, {"type": "chat_message", 
                                   "msg_type": "cnt_msg",
                                   "message": cnt_msg}
        )


    # Receive message from room group
    async def chat_message(self, event):
        msg_type = event["msg_type"]
        
        await self.send(text_data=json.dumps(event))

        if msg_type == "message" or msg_type == "follow" or msg_type == "like":
            await self.send_cnt_msg()


    @database_sync_to_async
    def get_cnt_message(self):
        person = Person.objects.get(username=self.user_name)

        return Activity.objects.filter(person=person, remote=1, is_read=False).count()


    @database_sync_to_async
    def update_user_incr(self, username):
        Person.objects.filter(username=username).update(online=F('online') + 1)

    @database_sync_to_async
    def update_user_decr(self, username):
        Person.objects.filter(username=username).update(online=F('online') - 1)

    @database_sync_to_async
    def update_message_is_read(self, username, message_id, is_read):
        person = Person.objects.get(username=username)

        if person is None:
            return
        
        Activity.objects.filter(person=person, ap_id=message_id, remote=1).update(is_read=is_read)
        # print(Activity.objects.get(person=person, ap_id=message_id, remote=1).is_read)


class NotificationsType(Enum):
    NEW_MSG = 0
    LIKE = 1
    FOLLOW = 2


class UserMessage():
    
    def __init__(self, person_username, msg_type, activity):
        if not isinstance(msg_type, NotificationsType):
            pass

        self.person_username = person_username
        # print(activity)
        actor = Person.objects.get(ap_id=activity.actor)

        if actor is None:
            pass

        self.body = {"type": "chat_message",
                     "actor_username": actor.username,
                     "actor_name": actor.name,}
        
        actp = activity.to_json(context=True)

        if msg_type == NotificationsType.NEW_MSG:
            self.body["url"] = activity.id
            self.body["msg_type"] = "message"
            self.body["message"] = activity.object.content
            self.body["activity"] = actp

        elif msg_type == NotificationsType.FOLLOW:
            self.body["url"] = activity.actor
            self.body["msg_type"] = "follow"
            self.body["message"] = "is now following you!"
            self.body["activity"] = actp

        elif msg_type == NotificationsType.LIKE:
            self.body["url"] = activity.object
            self.body["msg_type"] = "like"
            self.body["message"] = "liked you!"
            self.body["activity"] = actp


    def send_notification(self):
        channel_layer = get_channel_layer()

        asyncio.run(
            channel_layer.group_send(
                f"user_{self.person_username}",
                self.body
            ))
