from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class OLDataset(BaseModel):
    namespace: str
    name: str
    facets: dict[str, Any] = Field(default_factory=dict)


class OLRunFacets(BaseModel):
    nominalTime: Optional[dict[str, Any]] = None
    model_config = {"extra": "allow"}


class OLRun(BaseModel):
    runId: str
    facets: OLRunFacets = Field(default_factory=OLRunFacets)


class OLJobFacets(BaseModel):
    ownership: Optional[dict[str, Any]] = None
    model_config = {"extra": "allow"}


class OLJob(BaseModel):
    namespace: str
    name: str
    facets: OLJobFacets = Field(default_factory=OLJobFacets)


class OLRunEvent(BaseModel):
    """
    Validates the OpenLineage JSON that Airflow POSTs to /lineage/events.
    eventType must be COMPLETE or FAIL to be processed.
    """
    eventType: str
    eventTime: datetime
    run: OLRun
    job: OLJob
    inputs: list[OLDataset] = Field(default_factory=list)
    outputs: list[OLDataset] = Field(default_factory=list)
    producer: str = ""
    schemaURL: str = ""
    model_config = {"extra": "allow"}
