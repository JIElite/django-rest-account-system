from django.contrib import admin
from .models import UserProfile, ResetPasswordToken

admin.site.register(UserProfile)
admin.site.register(ResetPasswordToken)
