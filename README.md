<div align="center">

<br/>

```
██╗     ███████╗███████╗████████╗ ██████╗ ██████╗  █████╗ ███╗   ███╗
██║     ██╔════╝██╔════╝╚══██╔══╝██╔════╝ ██╔══██╗██╔══██╗████╗ ████║
██║     █████╗  █████╗     ██║   ██║  ███╗██████╔╝███████║██╔████╔██║
██║     ██╔══╝  ██╔══╝     ██║   ██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║
███████╗███████╗███████╗   ██║   ╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║
╚══════╝╚══════╝╚══════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
```

### *Where competitive programmers connect, compete, and grow.*

<br/>

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

<br/>

> **LeetGram** is a social media platform built for competitive programmers —  
> sync your coding profiles, challenge your friends, host contests, and climb the leaderboard.  
> All in one place.

<br/>

[✨ Features](#-features) • [🏗️ Architecture](#️-architecture) • [🚀 Getting Started](#-getting-started) • [📁 Project Structure](#-project-structure) • [🗄️ Database](#️-database-design) • [🔧 Tech Stack](#-tech-stack) • [🐳 Deployment](#-deployment)

<br/>

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 👤 User System
- Custom User model with email verification
- JWT-based authentication
- Badge & achievement system
- Public profile pages with activity feeds

### 🤝 Social Graph
- Send & accept friend requests
- Create private or public groups
- Group invitations & role management
- Activity feed across your network

### 🔗 Platform Integrations
- Sync **LeetCode**, **Codeforces**, **GeeksForGeeks** profiles
- Auto-refresh stats via background jobs
- Track total solved problems across all platforms

</td>
<td width="50%">

### ⚔️ Challenges
- Challenge any friend to a 1v1 coding battle
- Problems selected from shared solved history
- Tracks scores and outcomes in real-time

### 🏆 Contests
- Host individual or team-based contests
- Live leaderboard via WebSockets
- Submission tracking & scoring engine

### 📝 Revision Engine
- Spaced repetition system (SRS)
- Tracks mastery level & review intervals
- Smart reminders via scheduled notifications

### 📈 Ranking
- Daily, weekly, and all-time leaderboards
- Score = challenges won + contest points + problems solved + streak bonus
- Pre-computed snapshots for instant page loads

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
                        ┌─────────────────────────────────────┐
                        │              Nginx                   │
                        │         (Reverse Proxy)              │
                        └───────────┬─────────────┬───────────┘
                                    │             │
                          HTTP/REST │             │ WebSocket
                                    ▼             ▼
                        ┌───────────────┐  ┌─────────────────┐
                        │   Gunicorn    │  │     Daphne      │
                        │ (WSGI Server) │  │ (ASGI Server)   │
                        └───────┬───────┘  └────────┬────────┘
                                │                   │
                        ┌───────▼───────────────────▼────────┐
                        │           Django + DRF              │
                        │    (codearena project package)      │
                        └────────────────┬───────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                           ▼
    ┌──────────────────┐      ┌─────────────────┐        ┌─────────────────┐
    │   PostgreSQL     │      │      Redis       │        │  Celery Worker  │
    │   (Primary DB)   │      │  Cache · Broker  │        │  + Beat Scheduler│
    └──────────────────┘      │  Channel Layer   │        └─────────────────┘
                              └─────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Docker & Docker Compose *(for containerised setup)*

---

### ⚡ Quick Start (Local)

**1. Clone the repository**

```bash
git clone https://github.com/shivprasad31/LeetGram.git
cd LeetGram
```

**2. Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Set up environment variables**

```bash
cp .env.example .env
# Edit .env with your database, Redis, and secret key values
```

**5. Apply migrations**

```bash
python manage.py migrate
```

**6. Create a superuser**

```bash
python manage.py createsuperuser
```

**7. Start the development server**

```bash
python manage.py runserver
```

**8. Start Celery (in a separate terminal)**

```bash
# Worker
celery -A codearena worker -l info

# Beat scheduler (another terminal)
celery -A codearena beat -l info
```

> 🌐 App runs at `http://127.0.0.1:8000`

---

### 🐳 Docker Setup (Recommended)

```bash
git clone https://github.com/shivprasad31/LeetGram.git
cd LeetGram

cp .env.example .env
# Fill in your .env values

docker-compose up --build
```

This spins up all services automatically:

| Service | Role |
|---|---|
| `db` | PostgreSQL database |
| `redis` | Cache, Celery broker, Channels layer |
| `web` | Django via Gunicorn |
| `daphne` | ASGI server for WebSockets |
| `celery` | Background task worker |
| `beat` | Periodic task scheduler |
| `nginx` | Reverse proxy |

---

## 📁 Project Structure

```
LeetGram/
│
├── codearena/                  # Project settings, URL conf, routing, API router
│   ├── project_settings.py     # Main settings (Postgres, Redis, DRF, Channels, JWT)
│   ├── api.py                  # Central DRF router & auth endpoints
│   └── routing.py              # WebSocket URL routing
│
├── users/                      # Custom auth model, badges, verification, JWT
├── profiles/                   # Profile stats, activity tracking, public pages
├── friends/                    # Friend requests, friendship graph, APIs
├── groups/                     # Groups, memberships, invitations
├── problems/                   # Problem catalog, tags, difficulty, solved tracking
├── integrations/               # LeetCode / Codeforces / GFG sync (Celery tasks)
├── challenges/                 # 1v1 challenge engine, results, scoring
├── contests/                   # Contest hosting, teams, submissions, leaderboard
├── revision/                   # Spaced repetition lists, items, review scheduler
├── ranking/                    # Rank snapshots, score services, periodic refresh
├── notifications/              # Notification storage, delivery, WebSocket consumer
├── dashboard/                  # Landing page, user dashboard, settings
│
├── templates/                  # Shared base.html + all page templates
├── static/
│   ├── css/theme.css           # Design tokens, dark mode, warm gradients
│   └── js/app.js               # Theme persistence, counters, notification socket
│
├── docker/
│   └── entrypoint.sh           # Container startup script
├── nginx/
│   └── default.conf            # Nginx reverse proxy config
│
├── Dockerfile                  # Django app container image
├── docker-compose.yml          # Full service orchestration
├── manage.py                   # Django CLI entry point
└── requirements.txt            # Python dependencies
```

Each app follows the standard Django structure:

```
app_name/
├── models.py       # Database models & relationships
├── views.py        # Request handlers (template + API views)
├── serializers.py  # DRF serializers for API responses
├── services.py     # Business logic layer
├── urls.py         # URL patterns
└── tasks.py        # Celery background tasks (where applicable)
```

---

## 🗄️ Database Design

### Core Tables at a Glance

```
users_user
  ├── id (PK), email, username, password
  ├── is_verified, verification_code
  └── date_joined, last_login

profiles_profile  ──────────────────►  users_user (OneToOne)
  └── bio, avatar, total_solved, streak_days

friends_friendrequest  ──────────────►  users_user (sender, receiver)
  └── status: pending | accepted | rejected

friends_friendship  ─────────────────►  users_user (user1, user2)

problems_problem
  ├── title, slug, difficulty, platform
  └── tags (M2M → Tag), url

problems_solvedproblem  ────────────►  users_user + problems_problem
  └── solved_at, language

integrations_codingprofile  ────────►  users_user
  └── platform, username, total_solved, rating, last_synced_at

challenges_challenge  ──────────────►  users_user (challenger, opponent)
  └── status, deadline

challenges_challengeproblem  ───────►  challenges_challenge + problems_problem
  └── (3 random problems from shared solved history)

challenges_challengeresult  ────────►  challenges_challenge + users_user (winner)

contests_contest  ──────────────────►  users_user (created_by)
  └── title, start_time, end_time, is_team_based

revision_revisionitem  ─────────────►  users_user + problems_problem
  └── interval_days, mastery_level, next_review_at

ranking_ranksnapshot  ──────────────►  users_user
  └── period (daily|weekly|global), score, rank_position, snapshot_date

notifications_notification  ────────►  users_user (recipient)
  └── notification_type, message, is_read
```

---

## 🔧 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.11+ | Core language |
| **Web Framework** | Django 6.0.3 | MVC, ORM, templating |
| **REST API** | Django REST Framework 3.16 | Serializers, viewsets, API routing |
| **Authentication** | SimpleJWT 5.5 | JWT access + refresh tokens |
| **Real-time** | Django Channels 4.3 + Daphne | WebSocket notifications & live leaderboard |
| **Task Queue** | Celery 5.6 + Redis | Async jobs, periodic scheduling |
| **Database** | PostgreSQL (psycopg3) | Primary production database |
| **Caching** | Redis + django-redis | Query caching, session store |
| **HTTP Client** | httpx 0.28 | Async calls to external coding platforms |
| **HTML Parsing** | BeautifulSoup4 4.14 | Scraping GFG profile pages |
| **Image Handling** | Pillow 12.1 | Avatar & media uploads |
| **Rate Limiting** | django-ratelimit 4.1 | Protect auth endpoints |
| **Static Files** | WhiteNoise 6.12 | Serve static files efficiently |
| **Env Vars** | python-dotenv 1.2 | .env file support |
| **WSGI Server** | Gunicorn | Production HTTP serving |
| **ASGI Server** | Daphne | WebSocket & async HTTP |
| **Proxy** | Nginx | Reverse proxy, SSL termination |
| **Containers** | Docker + docker-compose | Reproducible deployment |
| **Frontend** | Bootstrap 5 + custom CSS/JS | Responsive UI with dark mode |

---

## ⚙️ Background Jobs (Celery)

LeetGram uses Celery for three categories of background work:

```
┌────────────────────────────────────────────────────────────┐
│                    Celery Beat (Scheduler)                  │
│  Triggers periodic tasks like a cron job                   │
└──────────────────────┬─────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 ┌─────────────┐ ┌──────────┐ ┌────────────────┐
 │ Profile     │ │ Revision │ │ Ranking        │
 │ Sync        │ │ Reminders│ │ Refresh        │
 │             │ │          │ │                │
 │ Fetch stats │ │ Check    │ │ Recompute      │
 │ from LC,CF, │ │ due items│ │ daily/weekly/  │
 │ GFG via API │ │ → notify │ │ global scores  │
 │ & scraping  │ │ users    │ │ → RankSnapshot │
 └─────────────┘ └──────────┘ └────────────────┘
```

---

## 🔌 External Integrations

| Platform | Method | Library |
|---|---|---|
| **LeetCode** | Unofficial GraphQL API | `httpx` |
| **Codeforces** | Public REST API | `httpx` |
| **GeeksForGeeks** | HTML page scraping | `httpx` + `BeautifulSoup4` |

> ⚠️ The LeetCode and GFG adapters rely on unofficial/public-facing endpoints. For production use, consider hardening these adapters or replacing with official integrations if they become available.

---

## 🔒 Security

- JWT authentication with access + refresh token rotation
- CSRF protection enabled for all template-rendered forms
- Rate limiting on `/accounts/login/` and `/accounts/register/` endpoints
- Environment variables for all secrets (never hardcoded)
- `DEBUG=False` enforced in production via `.env`

---

## 🌐 Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:password@localhost:5432/leetgram

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (for verification)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@email.com
EMAIL_HOST_PASSWORD=your-app-password
```

---

## 📸 Screenshots

> *Coming soon — UI previews of Dashboard, Challenge Arena, Leaderboard, and Profile pages.*

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

```bash
# Fork the repo, then:
git checkout -b feature/your-feature-name
git commit -m "feat: add your feature"
git push origin feature/your-feature-name
# Open a Pull Request
```

Please follow the existing code style and make sure all migrations are included.

---

## 📄 License

This project is open source. See [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ for competitive programmers

**[⬆ Back to top](#)**

</div>