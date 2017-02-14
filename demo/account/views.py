import hashlib
import datetime
import time
import uuid

from django.core.validators import validate_email
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError 
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
        
from .models import UserProfile, ResetPasswordToken
from .utils import is_valid_password


class UserInfoTestView(APIView): 
    # 這個 Class 是用來測試查看使用者資訊，僅供測試用
    # Precondition: None

    def get(self, request):
        if not request.user.is_authenticated():
            return Response({"auth":"Anonymous user"}, status=200)
            
        user = request.user
        user_info = {
            "username": user.username, 
            "nickname": user.userprofile.nickname
        }

        return Response(user_info, status=status.HTTP_200_OK)
   

class LoginView(APIView):
    # Precondition:
    #   1. 使用者尚未登入得情況
    #   2. Oauth 使用者不得透過這個 API 進行登入
    #   3. 登入欄位:
    #       username, password
    # 這裏沒有檢查 username format 是不是 email 是因為我們先排除了 Oauth 帳戶
    # 接著用 authenticate 去驗證帳戶是不是存在，所以可以不用驗證
    
    def __response_already_login(self, request):
        # 一定要有 request 參數，因為會對他做加工
        return Response({"error":"already_login"},
        status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        if request.user.is_authenticated():
            return self.__response_already_login(request)
        return render(request, "login.html")
    
    def post(self, request):
        # 這裏不用檢查是不是 Oauth 使用者是因為 Oauth 使用者預設的密碼
        # 是:  Password Not Set
        # 我們的服務唯二設定密碼的方法
        # 1. Change Password: 但是 Oauth 使用者不可以設定
        # 2. Reset Password: 因為用 username 去寄信，所以他也沒辦法收到
        # 因為 Oauth 使用者的 username 不會是 email format
        if request.user.is_authenticated():
            return self.__response_already_login(request)

        username = request.data.get("username", "")
        password = request.data.get("password", "")
        if username == "" or password == "":
            return Response({"error": "請輸入username, password"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"error": "帳戶驗證錯誤, 如果是 FB, Google 使用者，請改用 FB, Google 登入"},
            status=status.HTTP_401_UNAUTHORIZED)
         
        login(request, user)
        
        return redirect("/")
        # return Response(status=status.HTTP_200_OK)


class LogoutView(APIView):
    # TODO 為了測試方便有設定允許 GET, 但是實際上不行
    # Precondition:
    #   1. 使用者必須是已登入狀態, Oauth 使用者也可以登出
    #   2. 欄位: 沒有額外需求

    def __logout(self, request):
        if not request.user.is_authenticated():
            return Response({"error": "使用者尚未登入"},
            status=status.HTTP_401_UNAUTHORIZED)

        logout(request)
        return Response(status=status.HTTP_200_OK)

    def get(self, request):
        return self.__logout(request)
    
    def post(self, request):
        return self.__logout(request)


class GeneralSignUpView(APIView):
    # 這是一般使用者註冊的 API
    # Django User Model 只有保證 username 是 unique 這件事情
    # 利用 email 做為使用者的 username 註冊
    # 所以在驗證 username format 的時候要利用 email validator
    #
    # Precondition:
    #   1. 使用者必須是尚未登入的狀態
    #   2. username, email 不可與其他帳號重複
    
    def __response_block_already_login(self, request):
        return Response({"error":"使用者已登入"},
        status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        if request.user.is_authenticated():
            return self.__response_block_already_login(request)
        
        return render(request, "register.html")
    
    def post(self, request):
        if request.user.is_authenticated():
            return self.__response_block_already_login(request)
    
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        confirm_password = request.data.get("confirm_password", "")
        
        if username == "" or password == "" or confirm_password == "":
            return Response({"error": "欄位尚未填寫完整"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        # 一般註冊的 username 會是 email 形式, 所以我們必須 validate
        try:
            validate_email(username)
        except ValidationError:
            return Response({"error":"email_format_error"},
            status=status.HTTP_400_BAD_REQUEST)
        
        # password confirm validation
        if password != confirm_password:
            return Response({"error":"password_confirmation_failed"},
            status=status.HTTP_400_BAD_REQUEST)
        
        if not is_valid_password(password):
            return Response({"error":"密碼格式錯誤"},
            status=status.HTTP_400_BAD_REQUEST)

        # check user exists or not
        exist_username = User.objects.filter(username=username).exists()
        if exist_username:
            return Response({"error":"帳號已被註冊"},
            status=status.HTTP_409_CONFLICT)
        
        user = User.objects.create_user(username=username, password=password)
        # 同步 nickname, contact_email
        # 不用 check user profile model 是不是有建立連結
        # 因為我們已經利用 signal (.models.create_profile) 的方式跟 db 同步
        # 所以 user.save() 時，一定會確保 create_profile 這件事
        # nickname 經由切 email @ 前面的來得到
        profile = user.userprofile
        profile.nickname = user.username.split("@")[0]
        profile.contact_email = user.username
        profile.save()
        
        user = authenticate(username=username, password=password)
        login(request, user)

        return redirect("/")
        # return Response(status=status.HTTP_201_CREATED)

    
class ChangePasswordView(APIView):
    # Precondition:
    #   1. 使用者必須為登入狀態才可以更改密碼
    #   2. Oauth 使用者不可以更改密碼
    #
    # 修改完 Password 預設會被登出
    # 即使 Cookies 有記住新密碼也是一樣。

    permission_classes = (IsAuthenticated,)
    
    def __response_block_oauth_account(self, request):
        return Response({"error": "Oauth 帳戶不能修改密碼"}, 
        status=status.HTTP_403_FORBIDDEN)

    def get(self, request):
        if request.user.social_auth.exists():
            return self.__response_block_oauth_account(request)

        return render(request, "change_password.html")
    
    def post(self, request):
        if request.user.social_auth.exists():
            return self.__response_block_oauth_account(request)
        
        current_password = request.data.get('current_password', '')
        new_password = request.data.get('new_password', '')
        confirm_new_password = request.data.get('confirm_new_password', '')
        
        if current_password == "" or new_password == "" or confirm_new_password == "":
            return Response({"error": "請填寫完所有欄位"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
       
        if new_password != confirm_new_password:
            return Response({"error":"新密碼與確認密碼不一致"},
            status=status.HTTP_400_BAD_REQUEST)

        if not is_valid_password(new_password):
            return Response({"error":"密碼格式錯誤"},
            status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if not user.check_password(current_password):
            return Response({"error":"與目前密碼不符"},
            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        
        return Response(status=status.HTTP_200_OK)


class FindPasswordView(APIView):
    # Precondition:
    #   1. Oauth 使用者不可以尋找密碼
    #   2. 要填的資料: email
    #   填完後送出後，會寄一封信件給 user, 內容夾帶著 reset password
    #   的連結。
    
    def __create_reset_password_url(self, user):
        # TODO 怎麼 handle 創建失敗呢？
        
        email = user.username
        url_seed = (email + time.ctime() + "#$@%$").encode("utf-8")
        url_token = hashlib.sha256(url_seed).hexdigest()

        entry_token_seed = str(uuid.uuid1()).encode("utf-8")
        entry_token = hashlib.md5(entry_token_seed).hexdigest()[10:16]
        
        current_time = timezone.localtime(timezone.now())
        accessible_time = current_time + datetime.timedelta(minutes=10)
        
        # TODO 感覺上，因為已經知道 user 了，利用 user.resetpasswordtoken 似乎會比較快？
        # 但是會觸發 RelatedObjectDoesNotExist, 目前還不知道怎麼抓取
        rt, created = ResetPasswordToken.objects.get_or_create(user=user)
        rt.dynamic_url = url_token
        rt.entry_token = entry_token
        rt.expire_time = accessible_time
        
        try:
            rt.save()
        except:
            # IntegrityError
            # TODO 處理 dynamic url not unique
            rt = None

        return rt
    
    def __send_reset_password_url_email_to(self, user):
        user_email = user.username
        rt = user.resetpasswordtoken
        expire_local_time = timezone.localtime(rt.expire_time)

        email_content = (
                "Hi, {username}\n\n"

                "這是重置密碼的信件，點選下列連結可以進入重置頁面，\n"
                "如果您沒有使用忘記密碼的功能，請忽略本信。\n"
                "該連結必須輸入驗證碼用以驗證。\n\n"

                "下列為密碼重置連結，連結有效時間至: {expire_time}。\n"
                "{reset_password_url}\n\n"

                "驗證碼: {entry_token}\n\n"

                "感謝謝您的使用!\n"
                "----------------------------------------------\n"
                "Share Class 團隊"
        ).format(
                username=user.userprofile.nickname,
                expire_time=expire_local_time.strftime("%Y-%m-%d %H:%M"),
                reset_password_url="http://127.0.0.1:8000/accounts/reset_password/" + rt.dynamic_url,
                entry_token=rt.entry_token
        )

        # TODO check send_mail response
        send_mail(
                'Share Class 忘記密碼重置信',
                email_content,
                'service@jielite.tw',
                [user_email],
                fail_silently=False,
        )    
        
        return

    def get(self, request):
        return render(request, "find_password.html") 

    def post(self, request):
        email = request.data.get('email', '')

        if email == "":
            return Response({"error":"沒有email欄位"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        try:
            validate_email(email)
        except ValidationError:
            return Response({"error":"email 格式錯誤"},
            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(username=email)
        except User.DoesNotExist:
            return Response({"error": "沒有這個 Email 帳號"},
            status=status.HTTP_403_FORBIDDEN)
        else:
        # 因為 Oauth 帳戶沒有密碼，所以不提供這功能
            if user.social_auth.exists():
                return Response({"error":"Oauth user 不能使用這個功能"},
                status=status.HTTP_403_FORBIDDEN)
        
        if self.__create_reset_password_url(user) is None:
            return Response({"error": "創建連結失敗"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.__send_reset_password_url_email_to(user)

        return Response(status=200)
        

class ResetPasswordView(APIView):
    # Precondition:
    #   1. 使用者不可為登入狀態
    #   2. Oauth 使用者不可以尋找密碼
    #   
    #   不讓已登入的人來找密碼
    #   設定成功之後，沒有限制重置次數（在允許時間內都可以)
    
    def __response_block_already_login(self, request):
        return Response({"error":"使用者已登入，不可重置密碼"},
        status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, url_token):
        if request.user.is_authenticated():
            return self.__response_block_already_login(request)
        
        return render(request, "reset_password.html")

    def post(self, request, url_token):
        if request.user.is_authenticated():
            return self.__response_block_already_login(request)

        # Dynamic URL Token Validation
        try:
            user_reset_password_token = ResetPasswordToken.objects.get(dynamic_url=url_token)
        except ResetPasswordToken.DoesNotExist:
            return Response({"error": "無效的連結"},
            status=status.HTTP_403_FORBIDDEN)
        
        # check Dynamic URL lifetime
        if timezone.now() > user_reset_password_token.expire_time:
            return Response({"error": "驗證連結已超過時間"},
            status=status.HTTP_403_FORBIDDEN)

        new_password = request.data.get('new_password', '')
        confirm_new_password = request.data.get('confirm_new_password', '')
        entry_token = request.data.get('entry_token', '')
        
        # Empty Data Validation 
        if new_password == "" or confirm_new_password == "" or entry_token == "":
            return Response({"error":"欄位沒有填寫完整"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        password_confirm_failed = (new_password != confirm_new_password)
        entry_token_invalid = (entry_token != user_reset_password_token.entry_token)
        if password_confirm_failed or entry_token_invalid:
            return Response({"error":"輸入不一致或是驗證碼錯誤"},
            status=status.HTTP_400_BAD_REQUEST)
        
        if not is_valid_password(new_password):
            return Response({"error":"密碼格式錯誤"},
            status=status.HTTP_400_BAD_REQUEST)

        # Reset Password
        user = user_reset_password_token.user
        user.set_password(new_password)
        user.save()

        return Response(status=status.HTTP_200_OK)
