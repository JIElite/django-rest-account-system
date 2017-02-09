"""demo URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from .views import general_sign_up, sign_in, sign_out, get_user_info, change_password, find_password, reset_password 

urlpatterns = [
    url(r'^register$', general_sign_up),
    url(r'^login/$', sign_in),
    url(r'^logout/$', sign_out),
    url(r'^info/$', get_user_info),
    url(r'^change_password/$', change_password),
    url(r'^find_password/$', find_password),
    url(r'^reset_password/(?P<url_token>[0-9a-f]{64})/$', reset_password),
    
    url(r'', include('rest_framework_social_oauth2.urls'))
]
