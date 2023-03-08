from django.http import HttpResponse, HttpResponseRedirect

def is_visitor(user, username):
    return str(user) != str(username)

def response_error():
    response = HttpResponse()
    response.status_code = 403
    return response

def is_signin(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
