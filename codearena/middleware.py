from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseRedirect


class RedirectOnErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except (Http404, PermissionDenied):
            return self._redirect_home(request)
        except Exception:
            return self._redirect_home(request)

        if self._should_redirect_response(request, response.status_code):
            return self._redirect_home(request)
        return response

    def _redirect_home(self, request):
        if self._is_redirect_loop(request):
            return HttpResponse(status=204)
        request._error_redirected = True
        return HttpResponseRedirect(self._home_path())

    def _should_redirect_response(self, request, status_code):
        if not self._is_browser_request(request):
            return False
        if status_code < 400:
            return False
        if self._is_redirect_loop(request):
            return False
        return True

    def _is_browser_request(self, request):
        if request.path.startswith("/api/"):
            return False
        accept = request.headers.get("Accept", "")
        return not accept or "text/html" in accept or "*/*" in accept

    def _is_redirect_loop(self, request):
        return getattr(request, "_error_redirected", False) or request.path == self._home_path()

    def _home_path(self):
        return "/"
