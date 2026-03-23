from django.contrib import admin

from .models import Group, GroupChallenge, GroupInvite, GroupMembership, GroupTask

admin.site.register(Group)
admin.site.register(GroupMembership)
admin.site.register(GroupInvite)
admin.site.register(GroupTask)
admin.site.register(GroupChallenge)