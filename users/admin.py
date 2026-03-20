from django.contrib import admin

from .models import Badge, User, UserBadge

admin.site.register(User)
admin.site.register(Badge)
admin.site.register(UserBadge)

