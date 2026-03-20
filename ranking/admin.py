from django.contrib import admin

from .models import DailyRanking, GlobalLeaderboard, WeeklyRanking

admin.site.register(DailyRanking)
admin.site.register(WeeklyRanking)
admin.site.register(GlobalLeaderboard)

