from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class OmicsHubUserAdmin(UserAdmin):
    # `visible_columns` is dashboard state the user sets themselves, so it is shown for
    # support ("why is their table missing a column") but not editable from here.
    readonly_fields = ["visible_columns"]
    fieldsets = UserAdmin.fieldsets + (("OmicsHub", {"fields": ["visible_columns"]}),)
