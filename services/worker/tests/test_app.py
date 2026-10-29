from lozhka_worker.app import app, ping


def test_app_and_task_registered():
    assert "lozhka_worker.app.ping" in app.tasks or ping.name in app.tasks
