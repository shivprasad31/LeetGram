from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from challenges.api import ChallengeEventViewSet, ChallengeResultViewSet, ChallengeSubmissionViewSet, ChallengeViewSet
from contests.api import ContestLeaderboardViewSet, ContestSubmissionViewSet, ContestViewSet
from dashboard.api import DashboardPreferenceView, DashboardSummaryView
from friends.api import FriendRequestViewSet, FriendshipViewSet
from groups.api import GroupInviteViewSet, GroupMembershipViewSet, GroupViewSet
from notifications.api import NotificationViewSet
from problems.api import ProblemDifficultyViewSet, TagViewSet, ProblemViewSet, UserSolvedProblemViewSet
from profiles.api import ActivityViewSet, ProfileStatisticsViewSet
from ranking.api import DailyRankingViewSet, GlobalLeaderboardViewSet, WeeklyRankingViewSet
from revision.api import RevisionItemViewSet, RevisionListViewSet, RevisionNotesViewSet
from users.api import CurrentUserView, RegistrationView, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("profiles/statistics", ProfileStatisticsViewSet, basename="profile-statistics")
router.register("profiles/activity", ActivityViewSet, basename="profile-activity")
router.register("friends/requests", FriendRequestViewSet, basename="friend-request")
router.register("friends", FriendshipViewSet, basename="friendship")
router.register("groups", GroupViewSet, basename="group")
router.register("group-memberships", GroupMembershipViewSet, basename="group-membership")
router.register("group-invites", GroupInviteViewSet, basename="group-invite")
router.register("problem-difficulties", ProblemDifficultyViewSet, basename="problem-difficulty")
router.register("problem-tags", TagViewSet, basename="problem-tag")
router.register("problems", ProblemViewSet, basename="problem")
router.register("solved-problems", UserSolvedProblemViewSet, basename="solved-problem")
router.register("challenges", ChallengeViewSet, basename="challenge")
router.register("challenge-results", ChallengeResultViewSet, basename="challenge-result")
router.register("challenge-submissions", ChallengeSubmissionViewSet, basename="challenge-submission")
router.register("challenge-events", ChallengeEventViewSet, basename="challenge-event")
router.register("contests", ContestViewSet, basename="contest")
router.register("contest-submissions", ContestSubmissionViewSet, basename="contest-submission")
router.register("contest-leaderboard", ContestLeaderboardViewSet, basename="contest-leaderboard")
router.register("revision-lists", RevisionListViewSet, basename="revision-list")
router.register("revision-items", RevisionItemViewSet, basename="revision-item")
router.register("revision-notes", RevisionNotesViewSet, basename="revision-notes")
router.register("daily-rankings", DailyRankingViewSet, basename="daily-ranking")
router.register("weekly-rankings", WeeklyRankingViewSet, basename="weekly-ranking")
router.register("global-leaderboard", GlobalLeaderboardViewSet, basename="global-leaderboard")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("auth/register/", RegistrationView.as_view(), name="api-register"),
    path("auth/me/", CurrentUserView.as_view(), name="api-me"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/preferences/", DashboardPreferenceView.as_view(), name="dashboard-preferences"),
    path("", include(router.urls)),
]
