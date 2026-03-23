import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .utils import coerce_submission_datetime, normalize_problem_title, slug_or_value, to_json_bytes


class PlatformServiceError(Exception):
    pass


class BasePlatformService:
    user_agent = "codearena-sync/1.0"
    timeout = 15

    def _request(self, url, *, method="GET", payload=None, headers=None):
        final_headers = {"User-Agent": self.user_agent}
        if headers:
            final_headers.update(headers)
        request = Request(url=url, data=payload, headers=final_headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read(), getattr(response, "status", 200)
        except HTTPError as exc:
            raise PlatformServiceError(str(exc)) from exc
        except URLError as exc:
            raise PlatformServiceError(str(exc)) from exc

    def _get_json(self, url, *, method="GET", payload=None, headers=None):
        raw, _ = self._request(url, method=method, payload=payload, headers=headers)
        return json.loads(raw.decode("utf-8"))

    def _get_html(self, url, *, headers=None):
        raw, status = self._request(url, headers=headers)
        return BeautifulSoup(raw.decode("utf-8", errors="ignore"), "html.parser"), status

    def _filter_since(self, submissions, since):
        if not since:
            return submissions
        return [submission for submission in submissions if submission.get("solved_at") and submission["solved_at"] > since]

    def validate_username(self, username):
        return True


class CodeforcesService(BasePlatformService):
    api_url = "https://codeforces.com/api/user.status?handle={username}&from=1&count={count}"
    user_info_url = "https://codeforces.com/api/user.info?handles={username}"

    def validate_username(self, username):
        payload = self._get_json(self.user_info_url.format(username=quote(username)))
        return payload.get("status") == "OK" and bool(payload.get("result"))

    def fetch_solved_submissions(self, username, since=None, limit=100):
        payload = self._get_json(self.api_url.format(username=quote(username), count=limit))
        if payload.get("status") != "OK":
            raise PlatformServiceError(payload.get("comment", "Codeforces API request failed."))

        solved = []
        seen_ids = set()
        for item in payload.get("result", []):
            if item.get("verdict") != "OK":
                continue
            problem = item.get("problem") or {}
            contest_id = problem.get("contestId")
            index = problem.get("index")
            name = normalize_problem_title(problem.get("name"))
            if contest_id and index:
                platform_id = f"{contest_id}-{index}"
                url = f"https://codeforces.com/problemset/problem/{contest_id}/{index}"
            else:
                platform_id = slug_or_value(problem.get("problemsetName") or name)
                url = ""

            if not platform_id or platform_id in seen_ids or not name:
                continue
            seen_ids.add(platform_id)
            solved.append(
                {
                    "platform_id": platform_id,
                    "title": name,
                    "url": url,
                    "solved_at": coerce_submission_datetime(item.get("creationTimeSeconds")),
                }
            )

        return self._filter_since(solved, since)


class LeetCodeService(BasePlatformService):
    endpoint = "https://leetcode.com/graphql/"
    query = """
    query recentAcSubmissions($username: String!) {
      recentAcSubmissionList(username: $username) {
        id
        title
        titleSlug
        timestamp
      }
    }
    """
    validation_query = """
    query userProfile($username: String!) {
      matchedUser(username: $username) {
        username
      }
    }
    """

    def _post_graphql(self, payload):
        return self._get_json(
            self.endpoint,
            method="POST",
            payload=to_json_bytes(payload),
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com/"},
        )

    def validate_username(self, username):
        data = self._post_graphql(
            {
                "query": self.validation_query,
                "variables": {"username": username},
                "operationName": "userProfile",
            }
        )
        if data.get("errors"):
            raise PlatformServiceError(data["errors"][0].get("message", "LeetCode validation failed."))
        matched_user = (data.get("data") or {}).get("matchedUser")
        return bool(matched_user and matched_user.get("username"))

    def fetch_solved_submissions(self, username, since=None, limit=40):
        data = self._post_graphql(
            {
                "query": self.query,
                "variables": {"username": username},
                "operationName": "recentAcSubmissions",
            }
        )
        if data.get("errors"):
            raise PlatformServiceError(data["errors"][0].get("message", "LeetCode GraphQL request failed."))

        solved = []
        seen_ids = set()
        entries = (data.get("data") or {}).get("recentAcSubmissionList") or []
        for item in entries[:limit]:
            title = normalize_problem_title(item.get("title"))
            title_slug = item.get("titleSlug")
            platform_id = str(item.get("id") or title_slug or slug_or_value(title))
            if not title or not platform_id or platform_id in seen_ids:
                continue
            seen_ids.add(platform_id)
            solved.append(
                {
                    "platform_id": platform_id,
                    "title": title,
                    "url": f"https://leetcode.com/problems/{title_slug}/" if title_slug else "",
                    "solved_at": coerce_submission_datetime(item.get("timestamp")),
                }
            )

        return self._filter_since(solved, since)


class GFGService(BasePlatformService):
    profile_url = "https://authapi.geeksforgeeks.org/api-get/user-profile-info/?handle={username}&article_count=false&redirect=true"
    submissions_url = "https://practiceapi.geeksforgeeks.org/api/v1/user/problems/submissions/"

    def validate_username(self, username):
        try:
            payload = self._get_json(
                self.profile_url.format(username=quote(username)),
                headers={"Accept": "application/json, text/plain, */*"},
            )
        except PlatformServiceError as exc:
            if "HTTP Error 400" in str(exc) or "HTTP Error 404" in str(exc):
                return False
            raise
        return payload.get("message") == "data retrieved successfully"

    def fetch_solved_submissions(self, username, since=None, limit=100):
        payload = self._get_json(
            self.submissions_url,
            method="POST",
            payload=to_json_bytes({"handle": username}),
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://auth.geeksforgeeks.org",
                "Referer": f"https://auth.geeksforgeeks.org/user/{quote(username)}/practice/",
            },
        )
        if payload.get("status") != "success":
            raise PlatformServiceError(payload.get("message", "GeeksforGeeks submissions request failed."))

        solved = []
        seen_ids = set()
        for difficulty_name, difficulty_entries in (payload.get("result") or {}).items():
            if not isinstance(difficulty_entries, dict):
                continue
            for problem_id, item in difficulty_entries.items():
                title = normalize_problem_title(item.get("pname"))
                slug = item.get("slug")
                platform_id = str(problem_id or slug or slug_or_value(title))
                if not title or not platform_id or platform_id in seen_ids:
                    continue
                seen_ids.add(platform_id)
                solved.append(
                    {
                        "platform_id": platform_id,
                        "title": title,
                        "url": f"https://www.geeksforgeeks.org/problems/{slug}/1" if slug else "",
                        "difficulty": difficulty_name,
                        "solved_at": None,
                    }
                )
                if len(solved) >= limit:
                    return solved
        return solved


class HackerRankService(BasePlatformService):
    profile_url = "https://www.hackerrank.com/rest/contests/master/hackers/{username}/profile"
    recent_challenges_url = "https://www.hackerrank.com/rest/hackers/{username}/recent_challenges?limit={limit}"

    def validate_username(self, username):
        try:
            payload = self._get_json(
                self.profile_url.format(username=quote(username)),
                headers={"Accept": "application/json, text/plain, */*"},
            )
        except PlatformServiceError as exc:
            if "HTTP Error 404" in str(exc):
                return False
            raise
        return bool((payload.get("model") or {}).get("username"))

    def fetch_solved_submissions(self, username, since=None, limit=100):
        payload = self._get_json(
            self.recent_challenges_url.format(username=quote(username), limit=limit),
            headers={"Accept": "application/json, text/plain, */*"},
        )
        solved = []
        seen_ids = set()
        for item in payload.get("models", []):
            title = normalize_problem_title(item.get("name"))
            challenge_slug = item.get("ch_slug")
            platform_id = challenge_slug or slug_or_value(title)
            if not title or not platform_id or platform_id in seen_ids:
                continue
            seen_ids.add(platform_id)
            solved.append(
                {
                    "platform_id": platform_id,
                    "title": title,
                    "url": f"https://www.hackerrank.com{item.get('url', '')}" if item.get("url") else "",
                    "solved_at": coerce_submission_datetime(item.get("created_at")),
                }
            )
        return self._filter_since(solved, since)
