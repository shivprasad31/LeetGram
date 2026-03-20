from django.contrib import admin

from .models import Problem, ProblemDifficulty, ProblemTag, UserSolvedProblem

admin.site.register(ProblemDifficulty)
admin.site.register(ProblemTag)
admin.site.register(Problem)
admin.site.register(UserSolvedProblem)

