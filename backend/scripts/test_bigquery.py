"""
Test script: query BigQuery decom.dwd_event_log for v_thirdapp_open events.
Uses Application Default Credentials (gcloud auth application-default login).
"""

import json
from datetime import datetime
from google.cloud import bigquery

PROJECT_ID = "my-project-8584-jetonai"

SQL = """
SELECT REGEXP_EXTRACT(prop_params, r'kolUserId=(\\d+)') kol_user_id, count(*) AS cnt
FROM decom.dwd_event_log
WHERE date(logAt_timestamp) >= '2026-05-15'
  AND event_name = 'v_thirdapp_open'
  AND JSON_VALUE(args, '$.sf') != ''
  AND REGEXP_EXTRACT(prop_params, r'kolUserId=(\\d+)') = '2908973942389'
GROUP BY kol_user_id
"""


def serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def main():
    client = bigquery.Client(project=PROJECT_ID)

    query_job = client.query(SQL)
    results = query_job.result()

    rows = list(results)
    if not rows:
        print("No rows returned.")
        return

    row = dict(rows[0])
    print(json.dumps(row, indent=2, ensure_ascii=False, default=serialize))


if __name__ == "__main__":
    main()
