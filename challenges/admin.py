from django.contrib import admin

from .models import Challenge, ChallengeProblem, ChallengeResult

admin.site.register(Challenge)
admin.site.register(ChallengeProblem)
admin.site.register(ChallengeResult)

