import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, TemplateView

from groups.models import Group
from users.models import User

from .models import Challenge
from .execution import available_language_options, starter_code_for
from .services import (
    accept_challenge,
    build_challenge_payload,
    challenge_queryset_for,
    create_challenge,
    eligible_opponents_for,
    reject_challenge,
    user_groups_for,
)


def _challenge_for_user(user, challenge_id):
    challenge = get_object_or_404(challenge_queryset_for(user), pk=challenge_id)
    if user.id not in {challenge.challenger_id, challenge.opponent_id}:
        raise PermissionDenied
    return challenge


class ChallengePageView(LoginRequiredMixin, TemplateView):
    template_name = "challenges/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        all_challenges = list(challenge_queryset_for(user))
        pending_incoming = [challenge for challenge in all_challenges if challenge.opponent_id == user.id and challenge.status == Challenge.STATUS_PENDING]
        pending_outgoing = [challenge for challenge in all_challenges if challenge.challenger_id == user.id and challenge.status == Challenge.STATUS_PENDING]
        active_challenges = [challenge for challenge in all_challenges if challenge.status in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE}]
        finished_challenges = [challenge for challenge in all_challenges if challenge.status == Challenge.STATUS_FINISHED][:8]

        context.update(
            {
                "eligible_opponents": eligible_opponents_for(user),
                "user_groups": user_groups_for(user),
                "pending_incoming": pending_incoming,
                "pending_outgoing": pending_outgoing,
                "active_challenges": active_challenges,
                "open_room_count": len(active_challenges) + len(pending_outgoing),
                "finished_challenges": finished_challenges,
                "all_challenges": all_challenges[:12],
            }
        )
        return context


class ChallengeRoomView(LoginRequiredMixin, DetailView):
    template_name = "challenges/room.html"
    context_object_name = "challenge"

    def get_queryset(self):
        return challenge_queryset_for(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payload = build_challenge_payload(self.object, current_user=self.request.user)
        context["challenge_payload"] = payload
        context["challenge_payload_json"] = json.dumps(payload, cls=DjangoJSONEncoder)
        context["can_accept_here"] = self.request.user.id == self.object.opponent_id and self.object.status == Challenge.STATUS_PENDING
        context["challenge_accept_url"] = reverse("challenges:accept", kwargs={"challenge_id": self.object.id})
        context["challenge_reject_url"] = reverse("challenges:reject", kwargs={"challenge_id": self.object.id})
        context["starter_code"] = starter_code_for(payload.get("language", Challenge.LANGUAGE_PYTHON))
        context["monaco_cdn"] = getattr(settings, "CHALLENGE_MONACO_CDN", "")
        context["starter_templates_json"] = json.dumps(
            {
                option["value"]: starter_code_for(option["value"])
                for option in available_language_options()
            },
            cls=DjangoJSONEncoder,
        )
        return context


@require_POST
def send_challenge_view(request):
    if not request.user.is_authenticated:
        raise PermissionDenied

    try:
        opponent = get_object_or_404(User, pk=request.POST.get("opponent_id"))
        group = None
        if request.POST.get("group_id"):
            group = get_object_or_404(Group, pk=request.POST.get("group_id"))
        challenge = create_challenge(
            challenger=request.user,
            opponent=opponent,
            group=group,
            time_limit_minutes=30,
        )
        messages.success(request, f"Challenge sent to {opponent.username}.")
        return redirect(reverse("challenges:room", kwargs={"pk": challenge.id}))
    except ValidationError as exc:
        messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
        return redirect("challenges:index")


@require_POST
def accept_challenge_view(request, challenge_id):
    challenge = _challenge_for_user(request.user, challenge_id)
    try:
        accept_challenge(challenge, request.user)
        messages.success(request, "Challenge accepted. Join the room to start the battle.")
        return redirect(reverse("challenges:room", kwargs={"pk": challenge.id}))
    except ValidationError as exc:
        messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
        return redirect("challenges:index")


@require_POST
def reject_challenge_view(request, challenge_id):
    challenge = _challenge_for_user(request.user, challenge_id)
    try:
        reject_challenge(challenge, request.user)
        messages.info(request, "Challenge rejected.")
    except ValidationError as exc:
        messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
    return redirect("challenges:index")
