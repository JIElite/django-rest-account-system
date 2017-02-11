import hashlib
import datetime
import time
import uuid

from django.core.validators import validate_email
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError 
from django.core.mail import send_mail
from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
        
from .models import UserProfile, ResetPasswordToken



# 這個 Method 是用來測試查看使用者資訊，僅供測試用
# Precondition: None
@api_view(['GET'])
def get_user_info(request):
    if not request.user.is_authenticated():
        return Response({"auth":"Anonymous user"}, status=200)
        
    user = request.user
    user_info = {
        "username": user.username, 
        "nickname": user.userprofile.nickname
    }

    return Response(user_info, status=status.HTTP_200_OK)


# Precondition:
#   1. 使用者尚未登入得情況
#   2. Oauth 使用者不得透過這個 API 進行登入
#   3. 登入欄位:
#       username, password
@api_view(['GET', 'POST'])
def sign_in(request):
    if request.user.is_authenticated():
        return Response({"error":"already_login"}, status=status.HTTP_400_BAD_REQUEST)
    
    # handle GET method
    if request.method != "POST":
        return render(request, "login.html")
    
    # 欄位檢驗
    try:
        username = request.data["username"]
        password = request.data["password"]
    except KeyError:
        return Response({"error": "請輸入username, password"},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    
    # 檢驗是否為 Oauth 帳戶，因為 Oauth 帳戶不能夠過這個登入途徑
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({"error": "不存在這個使用者"},
        status=status.HTTP_401_UNAUTHORIZED)
    else:
        if user.social_auth.exists():
            return Response({"error":"Oauth Account, 請使用 Oauth 登入"},
            status=status.HTTP_403_FORBIDDEN)
    
    # 驗證身份 
    user = authenticate(username=username, password=password)
    if user is None:
        return Response({"error": "帳戶驗證錯誤"},
        status=status.HTTP_401_UNAUTHORIZED)
     
    login(request, user)
    
    return Response(status=status.HTTP_200_OK)
        

# TODO 為了測試方便有設定允許 GET, 但是實際上不行
# Precondition:
#   1. 使用者必須是已登入狀態, Oauth 使用者也可以登出
#   2. 欄位: 沒有額外需求
@api_view(['GET', 'POST'])
def sign_out(request):
    if not request.user.is_authenticated():
        return Response({"error": "使用者尚未登入"},
        status=status.HTTP_401_UNAUTHORIZED)

    logout(request)
    return Response(status=status.HTTP_200_OK)


# 這是一般使用者註冊的 API
# 利用 email 做為使用者的 username 註冊
# 所以在驗證 username format 的時候要利用 email validator
#
# Precondition:
#   1. 使用者必須是尚未登入的狀態
#   2. username, email 不可與其他帳號重複
@api_view(['GET', 'POST'])
def general_sign_up(request):
    # Django User Model 只有保證 username 是 unique 這件事情
    if request.user.is_authenticated():
        return Response({"error":"使用者已登入"},
        status=status.HTTP_400_BAD_REQUEST)
    
    if request.method != "POST":
        return render(request, "register.html")

    ### The following is for handing POST method 
    try:
        username = request.data["username"]
        password = request.data["password"]
        confirm_password = request.data["confirm_password"]
    except KeyError:
        return Response({"error": "欄位尚未填寫完整"},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    
    # check uniqueness of username
    exist_username = User.objects.filter(username=username).exists()
    if exist_username:
        return Response({"error":"Username 已被註冊"},
        status=status.HTTP_409_CONFLICT)
    
    # username format validation: 
    # 一般註冊的 username 會是 email 形式。
    try:
        validate_email(username)
    except ValidationError:
        return Response({"error":"email_format_error"},
        status=status.HTTP_400_BAD_REQUEST)
    
    # TODO password format validation
    
    # password confirm validation
    if password != confirm_password:
        return Response({"error":"password_confirmation_failed"},
        status=status.HTTP_400_BAD_REQUEST)
    
    # create user
    user = User(username=username)
    user.set_password(password)
    user.save()
    
    # 同步 nickname, contact_email
    # 不用 check user profile model 是不是有建立連結
    # 因為我們已經利用 signal (.models.create_profile) 的方式跟 db 同步
    # 所以 user.save() 時，一定會確保 create_profile 這件事
    profile = user.userprofile
    profile.nickname = user.username.split("@")[0]
    profile.contact_email = user.username
    profile.save()

    return Response(status=status.HTTP_201_CREATED)


# Precondition:
#   1. 使用者必須為登入狀態才可以更改密碼
#   2. Oauth 使用者不可以更改密碼
@api_view(['GET', 'POST'])
def change_password(request):
    if not request.user.is_authenticated():
        return Response(status=status.HTTP_401_UNAUTHORIZED)
     
    if request.user.social_auth.exists():
        return Response({"error": "Oauth 帳戶不能修改密碼"}, 
        status=status.HTTP_403_FORBIDDEN)

    # handle GET method 
    if request.method != "POST":
        return render(request, "change_password.html")

    try:
        current_password = request.data['current_password']
        new_password = request.data['new_password']
        confirm_new_password = request.data['confirm_new_password']
    except KeyError:
        return Response({"error": "請填寫完所有欄位"},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY)
   
    user = request.user
    if not user.check_password(current_password):
        return Response({"error":"與目前密碼不符"},
        status=status.HTTP_400_BAD_REQUEST)

    if new_password != confirm_new_password:
        return Response({"error":"新密碼與確認密碼不一致"},
        status=status.HTTP_400_BAD_REQUEST)

    # TODO password format validation
    
    user.set_password(new_password)
    user.save()

    return Response(status=status.HTTP_200_OK)

# Precondition:
#   1. Oauth 使用者不可以尋找密碼
@api_view(['GET', 'POST'])
def find_password(request):
    # missing password 要填的資料: email
    # 填完後送出後，會寄一封信件給 user, 內容夾帶著 reset password
    # 的連結。

    # handle GET method
    if request.method != "POST":
        return render(request, "find_password.html") 

    try:
        email = request.data['email']
        validate_email(email)
    except KeyError:
        return Response({"error":"沒有email欄位"},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except ValidationError:
        # 必須要 validate 因為 facebook 不一定能夠取得 email
        # 會造成多個 email == "" 的情況，後面的 User.objects.get
        # 就不能使用了
        return Response({"error":"email 格式錯誤"},
        status=status.HTTP_400_BAD_REQUEST)
    else:
        # TODO 因為 username is unique data, 這的 filter 可以改變寫法
        user_exist = User.objects.filter(username=email).exists()
        if not user_exist:
            return Response({"error": "沒有這個 email 的使用者"},
            status=status.HTTP_403_FORBIDDEN)
    
    # 因為 Oauth 帳戶沒有密碼，所以不提供這功能
    user = User.objects.get(username=email)
    if user.social_auth.exists():
        return Response({"error":"Oauth user 不能使用這個功能"},
        status=status.HTTP_403_FORBIDDEN)
    
    # generate reset password url
    url_seed = (email + time.ctime() + "#$@%$").encode("utf-8")
    url_token = hashlib.sha256(url_seed).hexdigest()

    entry_token_seed = str(uuid.uuid1()).encode("utf-8")
    entry_token = hashlib.md5(entry_token_seed).hexdigest()[10:16]
    
    current_time = timezone.localtime(timezone.now())
    accessible_time = current_time + datetime.timedelta(minutes=10)
    
    rt = ResetPasswordToken.objects.get(user=user)
    rt.dynamic_url = url_token
    rt.entry_token = entry_token
    rt.expire_time = accessible_time
    rt.save()

    # Send Email Message
    email_content = (
            "Hi, {username}\n\n"
            "已下是重置密碼的連結，如果您沒有使用忘記密碼的功能，請忽略本信\n"
            "下面的連結存活時間到 {expire_time} 為止\n"
            "另外，在該連結中必須輸入驗證碼用以驗證。\n\n"
            "密碼重置連結:\n"
            "{reset_password_url}\n"
            "驗證碼: {entry_token}\n\n"
            "感謝謝您的使用!\n"
            "From service@shareclass.com"
    ).format(
            username=user.userprofile.nickname,
            expire_time=accessible_time.strftime("%Y-%m-%d %H:%M"),
            reset_password_url="http://127.0.0.1:8000/accounts/reset_password/" + url_token,
            entry_token=entry_token
    )

    
    # TODO check send_mail response
    send_mail(
            'Share Class 忘記密碼重置信',
            email_content,
            'service@jielite.tw',
            [email],
            fail_silently=False,
    )    
     
    return Response(status=200)
        
# Precondition:
#   1. 使用者不可為登入狀態
#   2. Oauth 使用者不可以尋找密碼
@api_view(['GET', 'POST'])
def reset_password(request, url_token):
    # 設定成功之後，沒有限制操作次數

    # 不讓已登入的人來找密碼
    if request.user.is_authenticated():
        return Response({"error":"使用者已登入，不可重置密碼"},
        status=status.HTTP_400_BAD_REQUEST)

    if request.method != "POST":
        return render(request, "reset_password.html")
    
    # Dynamic URL Token Validation
    try:
        user_reset_password_token = ResetPasswordToken.objects.get(dynamic_url=url_token)
    except ResetPasswordToken.DoesNotExist:
        return Response({"error": "錯誤的 url"},
        status=status.HTTP_403_FORBIDDEN)
    
    # check Dynamic URL lifetime
    if timezone.now() > user_reset_password_token.expire_time:
        return Response({"error": "驗證連結已超過時間"},
        status=status.HTTP_403_FORBIDDEN)

    # Request Data Validation 
    try:
        new_password = request.data['new_password']
        confirm_new_password = request.data['confirm_new_password']
        entry_token = request.data['entry_token']
    except KeyError:
        return Response({"error":"欄位沒有填寫完整"},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    else:
        if new_password != confirm_new_password or\
        entry_token != user_reset_password_token.entry_token:
            return Response({"error":"輸入不一致或是驗證碼錯誤"},
            status=status.HTTP_400_BAD_REQUEST)
    
    # TODO Password Validation

    # Reset Password
    user = user_reset_password_token.user
    user.set_password(new_password)
    user.save()

    return Response(status=status.HTTP_200_OK)
