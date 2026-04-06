from app.models import LineageEvent
import logging

logger = logging.getLogger(__name__)


def write_event(event: LineageEvent) -> None:
    """
    STUB — Stage 3 will replace this with real Neo4j + Postgres writes.
    For now just logs the event so Stage 2 can be tested independently.
    """
    logger.info(f"[STUB] write_event called")
    logger.info(f"[STUB] job={event.job.name} run={event.run.run_id}")
    logger.info(f"[STUB] inputs={[d.uri for d in event.inputs]}")
    logger.info(f"[STUB] outputs={[d.uri for d in event.outputs]}")
