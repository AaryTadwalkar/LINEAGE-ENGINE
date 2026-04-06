from fastapi import APIRouter, HTTPException
from app.ingestion.pydantic_models import OLRunEvent
from app.ingestion.converter import ol_event_to_lineage_event
from app.storage.graph_writer import write_event
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lineage", tags=["ingestion"])


@router.post("/events", status_code=200)
def ingest_event(event: OLRunEvent):
    """
    Receives an OpenLineage event from Airflow or any OL-compatible source.
    Skips START events — only processes COMPLETE and FAIL.

    Returns 200 on success.
    Returns 422 if the JSON payload fails Pydantic validation (auto-handled by FastAPI).
    Returns 500 if the storage write fails.
    """
    logger.info(
        f"Received event: job={event.job.name} "
        f"run={event.run.runId} type={event.eventType}"
    )

    if event.eventType not in ("COMPLETE", "FAIL"):
        return {
            "status": "skipped",
            "reason": f"eventType {event.eventType} not processed"
        }

    try:
        lineage_event = ol_event_to_lineage_event(event)
        write_event(lineage_event)
        return {
            "status": "ok",
            "job": event.job.name,
            "run_id": event.run.runId
        }
    except Exception as e:
        logger.error(f"Failed to write event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Storage write failed: {str(e)}"
        )
