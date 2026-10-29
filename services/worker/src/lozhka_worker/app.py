"""Job-queue application (Procrastinate, PostgreSQL-backed).

Run a worker:   procrastinate --app=lozhka_worker.app.app worker --queues default,pipelines
Install schema: procrastinate --app=lozhka_worker.app.app schema --apply
Tables live in the ops schema (search_path below). Modules register their tasks by adding their
module path to import_paths.
"""
import procrastinate
from lozhka_common import get_settings

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=get_settings().database_url,
        kwargs={"options": "-c search_path=ops,public"},
    ),
    import_paths=[],  # e.g. "lozhka_supplier_docs.tasks", "lozhka_pipelines.tasks", ...
)


@app.task(queue="default")
def ping() -> str:
    """Smoke-test task: defer it to check that a worker is alive."""
    return "pong"
