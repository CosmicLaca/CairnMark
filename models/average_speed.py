"""Persist cumulative successful response timings by provider and model."""

import math
import sqlite3

from models.sqlite_store import SQLiteStore


SCHEMA = """
CREATE TABLE IF NOT EXISTS avg_speed (
    model_name TEXT PRIMARY KEY,
    response_time REAL NOT NULL DEFAULT 0,
    responses INTEGER NOT NULL DEFAULT 0
);
"""

STORE = SQLiteStore(
    "DATABASE_PATH",
    schema=SCHEMA,
    row_factory=sqlite3.Row,
)


def speed_tier(relative_percent):
    """Return the display tier for a model relative to the global average."""
    if relative_percent <= 33:
        return "very-fast"
    if relative_percent <= 66:
        return "fast"
    if relative_percent < 100:
        return "medium-fast"
    if relative_percent <= 300:
        return "regular"
    return "very-slow"


class AverageSpeedRepository:
    """Store totals and derive weighted relative response-speed statistics."""

    def __init__(self, store=STORE):
        self.store = store

    @staticmethod
    def model_key(provider, model_name):
        """Build the stable provider-qualified model key."""
        provider = str(provider or "").strip()
        model_name = str(model_name or "").strip()
        if not provider or not model_name:
            raise ValueError("Provider and model name are required.")
        return f"{provider}::{model_name}"

    def record(self, provider, model_name, response_time):
        """Add one completed response and return its current speed metadata."""
        model_key = self.model_key(provider, model_name)
        elapsed = float(response_time)
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Response time must be a non-negative number.")
        with self.store.transaction() as connection:
            connection.execute(
                """
                INSERT INTO avg_speed (model_name, response_time, responses)
                VALUES (?, ?, 1)
                ON CONFLICT(model_name) DO UPDATE SET
                    response_time = avg_speed.response_time + excluded.response_time,
                    responses = avg_speed.responses + 1
                """,
                (model_key, elapsed),
            )
        return self.for_model(provider, model_name)

    def statistics(self):
        """Return speed metadata for every model with at least one response."""
        rows = self.store.fetch(
            """
            SELECT model_name, response_time, responses
            FROM avg_speed
            WHERE responses > 0
            """
        )
        total_time = sum(float(row["response_time"]) for row in rows)
        total_responses = sum(int(row["responses"]) for row in rows)
        if total_responses <= 0:
            return {}
        global_average = total_time / total_responses
        if global_average <= 0:
            global_average = 1.0
        results = {}
        for row in rows:
            responses = int(row["responses"])
            average = float(row["response_time"]) / responses
            relative_percent = (average / global_average) * 100
            results[row["model_name"]] = {
                "average_response_time": average,
                "relative_speed_percent": relative_percent,
                "speed_tier": speed_tier(relative_percent),
                "responses": responses,
            }
        return results

    def for_model(self, provider, model_name):
        """Return current metadata for one model, if samples exist."""
        return self.statistics().get(self.model_key(provider, model_name))


AVERAGE_SPEEDS = AverageSpeedRepository()
