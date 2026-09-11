# Society Management — FastAPI Backend

Python/FastAPI rewrite of the Node.js Express `server`, using **PostgreSQL**, **SQLAlchemy**, **Pydantic**, and **RBAC**.

## Stack

| Concern | Choice |
|---------|--------|
| API | FastAPI |
| DB | PostgreSQL + SQLAlchemy (async) + Alembic |
| Auth | JWT (access 15m + refresh cookie 7d) |
| Passwords | passlib/bcrypt |
| Validation | Pydantic |
| Rate limit | slowapi (10 / 15 min on auth-sensitive routes) |

## Project layout (HMS-style)

```
Backend/
├── main.py              # FastAPI entry (uvicorn main:app)
├── seed.py
├── Constants/
├── Core/                # config, security
├── Database/
├── Dependencies/
├── Events/
├── Middleware/
├── Models/
├── Routers/
├── Schemas/
├── Services/
├── Utils/
├── alembic/
└── tests/
```

## Setup

1. Create a PostgreSQL database named `society_management`.
2. Copy/adjust `.env`:

```env
PORT=5000
NODE_ENV=development
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/society_management
CLIENT_ORIGIN=http://localhost:5173
JWT_SECRET=your-access-secret
JWT_REFRESH_SECRET=your-refresh-secret
```

3. Install and run:

```bash
cd Backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn main:app --reload --port 5000
```

Tables are also created automatically on startup via `init_db()` (handy for local dev). Prefer Alembic in production.

### Seed users

| Role | Email | Password |
|------|-------|----------|
| admin | `admin@society.com` | `Admin@123` |
| finance | `finance@society.com` | `Admin@123` |
| resident | `resident@society.com` | `Admin@123` |
| guard | `guard@society.com` | `Admin@123` |

## API (same URLs as Node)

### Auth — `/api/v1/auth`

- `POST /register` — admin JWT required
- `POST /login`
- `POST /refresh-token` — refresh cookie
- `POST /logout`
- `POST /forgot-password`
- `POST /reset-password`
- `POST /register-request`

### Profile — `/api/v1/{admin|finance|resident|guard}`

- `GET /profile`
- `PATCH /profile`
- `PATCH /change-password`

Response shape matches Node:

```json
{ "success": true, "message": "...", "data": {} }
```

## Roles (RBAC)

`admin` | `finance` | `resident` | `guard`

## Docs

- Swagger: http://localhost:5000/docs
- Health: http://localhost:5000/health
