from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from profiles.views import get_profiles, sync_now, update_profile_integrations
from users.views import ProfileSetupView, check_username, send_otp, verify_otp

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("codearena.api")),
    path("accounts/", include("users.urls")),
    path("send-otp/", send_otp, name="send-otp"),
    path("verify-otp/", verify_otp, name="verify-otp"),
    path("check-username/", check_username, name="check-username"),
    path("profile-setup/", ProfileSetupView.as_view(), name="profile-setup"),
    path("connect-profiles/", update_profile_integrations, name="connect-profiles"),
    path("get-profiles/", get_profiles, name="get-profiles"),
    path("sync-now/", sync_now, name="sync-now"),
    path("", include("dashboard.urls")),
    path("profiles/", include("profiles.urls")),
    path("friends/", include("friends.urls")),
    path("groups/", include("groups.urls")),
    path("problems/", include("problems.urls")),
    path("challenges/", include("challenges.urls")),
    path("revision/", include("revision.urls")),
    path("leaderboards/", include("ranking.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
