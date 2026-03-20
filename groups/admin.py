from django.contrib import admin

from .models import Group, GroupInvite, GroupMembership

admin.site.register(Group)
admin.site.register(GroupMembership)
admin.site.register(GroupInvite)

