from .celery_app import celery_app
from .pipeline import run_pipeline


@celery_app.task(name="analyze_repository")
def analyze_repository(report_id: int) -> None:
    run_pipeline(report_id)
