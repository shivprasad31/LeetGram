from django.contrib import admin

from .models import RevisionItem, RevisionList, RevisionNotes

admin.site.register(RevisionList)
admin.site.register(RevisionItem)
admin.site.register(RevisionNotes)

