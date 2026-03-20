from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from users.models import User

from .models import FriendRequest, Friendship
from .services import accept_friend_request, remove_friendship, send_friend_request


class FriendsPageView(LoginRequiredMixin, TemplateView):
    template_name = "friends/index.html"

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        try:
            if action == "send_request":
                receiver = get_object_or_404(User, pk=request.POST.get("receiver_id"))
                message = request.POST.get("message", "").strip()
                send_friend_request(request.user, receiver, message)
                messages.success(request, f"Friend request sent to {receiver.username}.")
            elif action == "accept_request":
                friend_request = get_object_or_404(
                    FriendRequest,
                    pk=request.POST.get("request_id"),
                    receiver=request.user,
                    status="pending",
                )
                accept_friend_request(friend_request)
                messages.success(request, f"You are now friends with {friend_request.sender.username}.")
            elif action == "decline_request":
                friend_request = get_object_or_404(
                    FriendRequest,
                    pk=request.POST.get("request_id"),
                    receiver=request.user,
                    status="pending",
                )
                friend_request.mark("declined")
                messages.info(request, f"Declined request from {friend_request.sender.username}.")
            elif action == "cancel_request":
                friend_request = get_object_or_404(
                    FriendRequest,
                    pk=request.POST.get("request_id"),
                    sender=request.user,
                    status="pending",
                )
                friend_request.mark("cancelled")
                messages.info(request, f"Cancelled request to {friend_request.receiver.username}.")
            elif action == "remove_friend":
                friend = get_object_or_404(User, pk=request.POST.get("friend_id"))
                removed = remove_friendship(request.user, friend)
                if removed:
                    messages.info(request, f"Removed {friend.username} from your friends list.")
                else:
                    messages.warning(request, f"{friend.username} is not in your friends list.")
            else:
                messages.error(request, "Unknown friends action.")
        except ValidationError as exc:
            messages.error(request, exc.message if hasattr(exc, "message") else str(exc))

        return redirect(self.get_return_url())

    def get_return_url(self):
        base_url = reverse("friends:index")
        query = self.request.GET.get("q", "").strip()
        if not query:
            return base_url
        return f"{base_url}?{urlencode({'q': query})}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        search_query = self.request.GET.get("q", "").strip()

        friendships = Friendship.objects.filter(Q(user_one=user) | Q(user_two=user)).select_related("user_one", "user_two")
        pending_received = FriendRequest.objects.filter(receiver=user, status="pending").select_related("sender")
        pending_sent = FriendRequest.objects.filter(sender=user, status="pending").select_related("receiver")

        friend_entries = []
        friend_ids = set()
        for friendship in friendships:
            friend = friendship.user_two if friendship.user_one == user else friendship.user_one
            friend_entries.append({"friend": friend, "friendship": friendship})
            friend_ids.add(friend.id)

        pending_received_map = {friend_request.sender_id: friend_request for friend_request in pending_received}
        pending_sent_map = {friend_request.receiver_id: friend_request for friend_request in pending_sent}

        student_queryset = User.objects.exclude(pk=user.pk)
        if search_query:
            student_queryset = student_queryset.filter(
                Q(username__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(bio__icontains=search_query)
            )

        student_queryset = student_queryset.order_by("-rating", "username")[:18]
        discoverable_students = []
        for student in student_queryset:
            discoverable_students.append(
                {
                    "student": student,
                    "is_friend": student.id in friend_ids,
                    "pending_received": pending_received_map.get(student.id),
                    "pending_sent": pending_sent_map.get(student.id),
                }
            )

        context.update(
            {
                "search_query": search_query,
                "friend_entries": friend_entries,
                "friendships": friendships,
                "pending_received": pending_received,
                "pending_sent": pending_sent,
                "discoverable_students": discoverable_students,
            }
        )
        return context
