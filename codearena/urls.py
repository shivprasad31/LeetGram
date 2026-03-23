from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from profiles.views import get_profiles, sync_now, update_profile_integrations

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("codearena.api")),
    path("accounts/", include("users.urls")),
    path("connect-profiles/", update_profile_integrations, name="connect-profiles"),
    path("get-profiles/", get_profiles, name="get-profiles"),
    path("sync-now/", sync_now, name="sync-now"),
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
