from django.contrib.auth.models import User

def save_profile(backend, *args, **kwargs):
    
    username = kwargs.get('username')
    details = kwargs.get('details')
    email = details.get('email')
    fullname = details.get('fullname')

    # clean email to disable find password
    user = User.objects.get(username=username)
    if user.email != "":
        user.email = ""
        user.save()


