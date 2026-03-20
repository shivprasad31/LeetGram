from django.contrib import admin

from .models import ProfileStatistics, UserActivity

admin.site.register(ProfileStatistics)
admin.site.register(UserActivity)

