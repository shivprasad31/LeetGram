from django.contrib import admin

from .models import Contest, ContestLeaderboard, ContestParticipant, ContestProblem, ContestSubmission, ContestTeam

admin.site.register(Contest)
admin.site.register(ContestProblem)
admin.site.register(ContestTeam)
admin.site.register(ContestParticipant)
admin.site.register(ContestSubmission)
admin.site.register(ContestLeaderboard)

