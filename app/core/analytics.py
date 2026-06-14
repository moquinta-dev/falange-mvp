"""PostgreSQL analytics views consumed by Grafana.

These views power the FalangeLabs funnel dashboard:

- ``vw_conversation_metrics``: one row per conversation with lifecycle marks and
  handle time (first to last message).
- ``vw_funnel_metrics``: single aggregate row with the headline KPIs
  (% completed without human, % handoff, average handle time).
- ``vw_daily_metrics``: daily series for trend panels.
- ``vw_lead_funnel``: lead counts per commercial-funnel status.

The backend owns the schema, so it (re)creates these views on startup. The
Grafana read-only role inherits ``SELECT`` via DEFAULT PRIVILEGES configured by
the infra stack, and we also grant explicitly here to be safe.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_CONVERSATION_METRICS_VIEW = """
CREATE OR REPLACE VIEW vw_conversation_metrics AS
SELECT
    c.id AS conversation_id,
    c.channel,
    c.state,
    c.created_at,
    c.updated_at,
    c.completed_at,
    c.handed_off_at,
    (c.state = 'completed') AS completed_without_human,
    (c.handed_off_at IS NOT NULL OR c.state = 'handoff') AS handed_off,
    (c.state IN ('completed', 'handoff') OR c.handed_off_at IS NOT NULL) AS is_terminal,
    mm.first_message_at,
    mm.last_message_at,
    EXTRACT(EPOCH FROM (mm.last_message_at - mm.first_message_at)) AS handle_time_seconds
FROM conversations c
LEFT JOIN (
    SELECT
        conversation_id,
        MIN(created_at) AS first_message_at,
        MAX(created_at) AS last_message_at
    FROM messages
    GROUP BY conversation_id
) mm ON mm.conversation_id = c.id;
"""

_FUNNEL_METRICS_VIEW = """
CREATE OR REPLACE VIEW vw_funnel_metrics AS
SELECT
    COUNT(*) AS total_conversations,
    COUNT(*) FILTER (WHERE is_terminal) AS terminal_conversations,
    COUNT(*) FILTER (WHERE completed_without_human) AS completed_without_human,
    COUNT(*) FILTER (WHERE handed_off) AS handed_off,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE completed_without_human)
        / NULLIF(COUNT(*) FILTER (WHERE is_terminal), 0),
        2
    ) AS pct_completed_without_human,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE handed_off)
        / NULLIF(COUNT(*) FILTER (WHERE is_terminal), 0),
        2
    ) AS pct_handoff,
    ROUND(
        AVG(handle_time_seconds) FILTER (WHERE is_terminal)::numeric,
        2
    ) AS avg_handle_time_seconds
FROM vw_conversation_metrics;
"""

_DAILY_METRICS_VIEW = """
CREATE OR REPLACE VIEW vw_daily_metrics AS
SELECT
    date_trunc('day', created_at) AS day,
    COUNT(*) AS conversations,
    COUNT(*) FILTER (WHERE completed_without_human) AS completed_without_human,
    COUNT(*) FILTER (WHERE handed_off) AS handed_off,
    ROUND(
        AVG(handle_time_seconds) FILTER (WHERE is_terminal)::numeric,
        2
    ) AS avg_handle_time_seconds
FROM vw_conversation_metrics
GROUP BY 1
ORDER BY 1;
"""

_LEAD_FUNNEL_VIEW = """
CREATE OR REPLACE VIEW vw_lead_funnel AS
SELECT
    status,
    COUNT(*) AS leads
FROM leads
GROUP BY status;
"""

_VIEWS = (
    _CONVERSATION_METRICS_VIEW,
    _FUNNEL_METRICS_VIEW,
    _DAILY_METRICS_VIEW,
    _LEAD_FUNNEL_VIEW,
)


def apply_analytics_objects(engine: Engine) -> None:
    """Create/replace the analytics views and grant the read-only role."""

    from app.core.settings import get_settings

    grafana_role = get_settings().grafana_db_role

    with engine.begin() as connection:
        for statement in _VIEWS:
            connection.execute(text(statement))

        role_exists = connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": grafana_role},
        ).scalar()

        if role_exists:
            connection.execute(
                text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{grafana_role}"')
            )
            logger.info("Granted SELECT on analytics views to role '%s'", grafana_role)
        else:
            logger.info(
                "Grafana read-only role '%s' not found; skipping grants", grafana_role
            )
