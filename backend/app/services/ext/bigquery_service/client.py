"""
BigQuery client for querying external project data.
Uses Application Default Credentials (ADC).
"""

from datetime import date
from functools import lru_cache

from google.cloud import bigquery

from app.core.config import settings


@lru_cache(maxsize=1)
def get_client() -> bigquery.Client:
    return bigquery.Client(project=settings.ext_bigquery_project_id)
