from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("codearena.api")),
    path("accounts/", include("users.urls")),
    path("", include("dashboard.urls")),
    path("profiles/", include("profiles.urls")),
    path("friends/", include("friends.urls")),
    path("groups/", include("groups.urls")),
    path("problems/", include("problems.urls")),
    path("challenges/", include("challenges.urls")),
    path("contests/", include("contests.urls")),
    path("revision/", include("revision.urls")),
    path("leaderboards/", include("ranking.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

