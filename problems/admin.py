from django.contrib import admin

from .models import Problem, ProblemDifficulty, Tag, UserSolvedProblem, PlatformProblem

admin.site.register(ProblemDifficulty)
admin.site.register(Tag)
admin.site.register(PlatformProblem)
admin.site.register(Problem)
admin.site.register(UserSolvedProblem)

