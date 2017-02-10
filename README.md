# Django REST Account System

## Introduction
包含一般登入登入，Google, Facebook Oauth

## Configuration
這裡有兩個檔案需要設定
- aws_credentials.py: 裡面要設定 SES 的 IAM user
- oauth_credentials.py: 要設定你在 Google, Facebook 創建 Oauth API 的憑證

## Environment Initialization
```
create virtual environment for python
$ virtualenv -p python env
$ source env/bin/activate
$ pip install -r requirements.txt

database synchronization
$ cd demo
$ ./manage.py migrate
$ ./manage.py makemigrations account
$ ./manage.py migrate
```

## Run Server
```
$ ./manage.py runserver
```

## Endpoint
使用方式： 127.0.0.1:8000/accounts/register/

- /accounts/register/: 註冊帳號
- /accounts/login/: 登入, 要注意的是 Facebook Oauth 登入的時候，domain 只允許 localhost:8000, not 127.0.0.1
- /accounts/logout/: 登出, 必須是在登入中
- /accounts/info/: 查看使用者 username, email
- /accounts/change_password/: 修改密碼，必須先輸入原本的密碼, 且處於登入中的狀態
- /accounts/find_password/: 尋找密碼, 處於尚未登入的情況才可以
- /accounts/reset_password/{token}/: 使用尋找密碼功能後，夾帶在 email 中的連結。



