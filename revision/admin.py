from django.contrib import admin

from .models import RevisionItem, RevisionList, RevisionNote

admin.site.register(RevisionList)
admin.site.register(RevisionItem)
admin.site.register(RevisionNote)

