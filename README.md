# Dictation

Webapp luyện nghe tiếng Anh bằng chép chính tả cho người Việt. Yêu cầu: [`docs/srs-mvp.md`](docs/srs-mvp.md) · Plan: [`plans/260918-1535-dictation-mvp/plan.md`](plans/260918-1535-dictation-mvp/plan.md) · UI: [`docs/ui/`](docs/ui/).

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `api/` | FastAPI + SQLAlchemy 2 (async) + Alembic; worker nền (`python -m app.worker`) dùng bảng `jobs` trong Postgres làm hàng đợi |
| `web/` | React 19 + Vite + TypeScript strict + TanStack Query + Tailwind v4 + shadcn/ui; client API sinh từ `api/openapi.json` |
| `docker-compose.yml` | `web` (Caddy: SPA + proxy `/api`) · `api` · `worker` · `postgres` |

## Yêu cầu

- Docker (Compose v2)
- [uv](https://docs.astral.sh/uv/) — tự cài Python 3.12 cho `api/`
- Node 24 + npm

## Chạy cả stack

```bash
cp .env.example .env            # tuỳ chỉnh cổng nếu trùng: POSTGRES_HOST_PORT (5434), WEB_HOST_PORT (8080)
docker compose up -d
open http://localhost:8080      # trang chủ hiện "API OK · DB ok"
```

API tự chạy `alembic upgrade head` khi khởi động; worker đợi API healthy.

## Phát triển

```bash
docker compose up -d postgres   # Postgres ở localhost:5434 (tạo sẵn DB dictation + dictation_test)

# API — http://localhost:8000/docs
cd api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run python -m app.worker     # worker (terminal khác)

# Web — http://localhost:5173 (proxy /api → :8000)
cd web
npm install
npm run dev
```

## Kiểm tra (giống CI)

```bash
# api/
uv run ruff check . && uv run ruff format --check . && uv run mypy app tests && uv run pytest

# web/
npm run lint && npm run typecheck && npm test
```

## Đổi API → cập nhật client TS

```bash
cd api && uv run python -m app.cli export-openapi > openapi.json
cd ../web && npm run gen:api
```

CI báo lỗi nếu `api/openapi.json` hoặc `web/src/lib/api/schema.d.ts` lệch với code.

## Migration mới

```bash
cd api && uv run alembic revision --autogenerate -m "describe change"
```

Kiểm tra lại file sinh ra (phải có `downgrade`), rồi chạy `uv run pytest` — test suite dựng schema bằng Alembic và chạy thử downgrade/upgrade.
