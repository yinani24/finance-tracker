"""Vercel entrypoint.

Vercel's Python runtime serves an ASGI app exported as `app` from a file under
`api/`. The FastAPI application is built in `app.main`, so this only re-exports
it — keeping deployment configuration out of the application itself.

Only the stateless recommendation endpoints are reachable in practice: they are
the sole routes that need no database, and the client-only flow calls nothing
else. The rest of the app is present but idle without a configured database.
"""

from app.main import app

__all__ = ["app"]
