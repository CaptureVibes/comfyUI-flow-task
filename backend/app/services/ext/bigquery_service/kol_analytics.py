"""
KOL analytics queries against the external project's BigQuery dataset.
"""

from datetime import date

from google.cloud import bigquery

from .client import get_client


def get_kol_thirdapp_open_count(
    kol_user_id: str,
    start_date: date,
    end_date: date,
) -> int:
    """
    Count v_thirdapp_open events for a given KOL within [start_date, end_date].
    Returns the event count, or 0 if no data found.
    """
    sql = """
        SELECT
            REGEXP_EXTRACT(prop_params, r'kolUserId=(\\d+)') AS kol_user_id,
            COUNT(*) AS cnt
        FROM decom.dwd_event_log
        WHERE DATE(logAt_timestamp) BETWEEN @start_date AND @end_date
          AND event_name = 'v_thirdapp_open'
          AND JSON_VALUE(args, '$.sf') != ''
          AND REGEXP_EXTRACT(prop_params, r'kolUserId=(\\d+)') = @kol_user_id
        GROUP BY kol_user_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date.isoformat()),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date.isoformat()),
            bigquery.ScalarQueryParameter("kol_user_id", "STRING", kol_user_id),
        ]
    )

    client = get_client()
    rows = list(client.query(sql, job_config=job_config).result())

    if not rows:
        return 0
    return rows[0]["cnt"]
