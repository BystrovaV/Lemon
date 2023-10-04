from django.urls import re_path
import lemon.websockets.consumers as consumers

websocket_urlpatterns = [
    re_path(r"ws/users/(?P<user_name>\w+)/$", consumers.UserConsumer.as_asgi()),
]