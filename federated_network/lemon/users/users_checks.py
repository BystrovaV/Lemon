from django.http import HttpResponse


def is_visitor(user, username):
    return str(user) != str(username)

def response_error():
    response = HttpResponse()
    response.status_code = 403
    return response