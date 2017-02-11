from django.contrib.auth.models import User
from .models import UserProfile

# 這個 pipeline 只有在處理 Oauth Account 的時候會用到
def save_profile(backend, *args, **kwargs):
    
    username = kwargs.get('username')
    details = kwargs.get('details')
    email = details.get('email')
    fullname = details.get('fullname')

    # clean email to disable find password
    user = User.objects.get(username=username)
    
    # init user profile
    profile = user.userprofile
    if profile.nickname == "":
        profile.nickname = fullname

    if profile.contact_email == "":
        profile.contact_email = email

    profile.save()
    


