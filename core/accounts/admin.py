from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "phone", "is_staff", "is_active")
    list_filter = UserAdmin.list_filter + ("role",)
    fieldsets = UserAdmin.fieldsets + (("VTU", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("VTU", {"fields": ("email", "role", "phone")}),)