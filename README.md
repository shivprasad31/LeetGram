# CodeArena

CodeArena is a Django + DRF platform for programming students who want social accountability, challenge-based competition, contest hosting, revision tooling, external coding-profile sync, and live leaderboard updates in one product.

## Phase Map

1. Project setup
   The project is scaffolded as `codearena` with the required apps: `users`, `profiles`, `friends`, `groups`, `problems`, `integrations`, `challenges`, `contests`, `revision`, `ranking`, `notifications`, and `dashboard`.

2. Database design
   Each app owns its production-oriented models, constraints, indexes, and relationships. The custom `User` model lives in `users`, social graph models live in `friends` and `groups`, coding-domain entities live in `problems`, and competitive/revision flows live in `challenges`, `contests`, `revision`, and `ranking`.

3. Integrations
   `integrations/services.py` contains provider adapters for LeetCode, Codeforces, and GeeksForGeeks, while `integrations/tasks.py` runs imports in Celery.

4. Social features
   Friendship requests, friendships, groups, notifications, and profile activity feeds are all wired through services and APIs.

5. Core challenge system
   Challenge creation selects three random shared solved problems between two users, stores them in `ChallengeProblem`, and records outcomes in `ChallengeResult`.

6. Contests and teams
   Contests support individual or team-based participation via `ContestTeam`, `ContestParticipant`, `ContestSubmission`, and `ContestLeaderboard`.

7. Revision engine
   `RevisionItem` uses spaced-repetition metadata, and `revision/services.py` updates intervals and mastery state.

8. Ranking
   Daily, weekly, and global standings are calculated from challenge wins, contest points, solved counts, and streak bonuses.

9. Frontend system
   Templates share a single `base.html`, a Bootstrap 5 shell, a warm minimal palette, Poppins + Inter typography, dark mode support, and lightweight animations via `static/css/theme.css` and `static/js/app.js`.

10. Security and performance
    JWT is enabled through SimpleJWT, CSRF stays enabled for template forms, rate limiting is applied to sensitive endpoints, Redis-backed cache/channels are supported, and Celery + beat are configured for async workloads.

11. Deployment
    The repo includes `Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh`, and `nginx/default.conf` for a Postgres + Redis + Gunicorn + Daphne + Celery deployment topology.

## File Structure

- `codearena/project_settings.py`
  Main project settings with PostgreSQL/SQLite fallback, Redis/LocMem fallback, DRF, Channels, Celery, static/media, and JWT configuration.
- `codearena/api.py`
  Central DRF router and auth endpoints.
- `codearena/routing.py`
  WebSocket URL routing for notifications and live contest updates.
- `templates/`
  Shared design system and page templates for landing, dashboard, profiles, friends, groups, problems, challenges, contests, revision, ranking, and auth pages.
- `static/css/theme.css`
  Global visual system, theme tokens, card styles, warm gradients, and dark-mode overrides.
- `static/js/app.js`
  Theme persistence, animated counters, progress-bar animation, and live notification socket hookup.
- `users/`
  Custom auth model, badges, verification flow, signup/login views, and user APIs.
- `profiles/`
  Profile statistics, user activity tracking, and public profile page/API.
- `friends/`
  Friend requests, friendships, and request/accept/remove APIs.
- `groups/`
  Group entities, memberships, invites, list/detail views, and group APIs.
- `problems/`
  Problem catalog, tags, difficulty taxonomy, solved problem tracking, recommendations, and APIs.
- `integrations/`
  External coding profile connections plus Celery-driven synchronization.
- `challenges/`
  Challenge orchestration, challenge problems, results, views, and APIs.
- `contests/`
  Contest hosting, team participation, submissions, live leaderboard logic, pages, and APIs.
- `revision/`
  Revision lists, items, notes, reminder tasks, and review APIs.
- `ranking/`
  Snapshot ranking models, score services, scheduled refresh tasks, pages, and APIs.
- `notifications/`
  Notification storage, delivery service, API, and WebSocket consumer.
- `dashboard/`
  Landing page, user dashboard, settings page, preferences model, and summary APIs.

## Local Run

1. Create an environment from `.env.example`.
2. Install requirements.
3. Run `python manage.py migrate`.
4. Start Django with `python manage.py runserver`.
5. Start Celery with `celery -A codearena worker -l info` and `celery -A codearena beat -l info`.

## Notes

- SQLite fallback is enabled for developer convenience, but PostgreSQL is the intended production database.
- Redis fallback is optional for local development; when Redis is absent, cache, channel layer, and Celery eager mode fall back to developer-friendly behavior.
- The LeetCode and GeeksForGeeks integrations use public-facing endpoints and HTML parsing where official APIs are limited, so production deployments should harden or replace those adapters as needed.
