"""Persist cumulative successful response timings by provider and model."""

import math
import sqlite3

from models.sqlite_store import SQLiteStore


SCHEMA = """
CREATE TABLE IF NOT EXISTS avg_speed (
    model_name TEXT PRIMARY KEY,
    response_time REAL NOT NULL DEFAULT 0,
    responses INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0
);
"""

STORE = SQLiteStore(
    "DATABASE_PATH",
    schema=SCHEMA,
    columns={
        "avg_speed": {
            "output_tokens": "INTEGER NOT NULL DEFAULT 0",
        }
    },
    row_factory=sqlite3.Row,
)


def speed_tier(relative_percent):
    """Return the display tier for a model relative to the global average."""
    if relative_percent >= 300:
        return "very-fast"
    if relative_percent >= 150:
        return "fast"
    if relative_percent > 100:
        return "medium-fast"
    if relative_percent >= (100 / 3):
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

    def record(self, provider, model_name, response_time, output_tokens):
        """Add one completed response and return its current speed metadata."""
        model_key = self.model_key(provider, model_name)
        elapsed = float(response_time)
        tokens = int(output_tokens or 0)
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Response time must be a non-negative number.")
        if elapsed == 0 or tokens <= 0:
            return self.for_model(provider, model_name)
        with self.store.transaction() as connection:
            connection.execute(
                """
                INSERT INTO avg_speed (
                    model_name, response_time, responses, output_tokens
                )
                VALUES (?, ?, 1, ?)
                ON CONFLICT(model_name) DO UPDATE SET
                    response_time = avg_speed.response_time + excluded.response_time,
                    responses = avg_speed.responses + 1,
                    output_tokens = avg_speed.output_tokens + excluded.output_tokens
                """,
                (model_key, elapsed, tokens),
            )
        return self.for_model(provider, model_name)

    def statistics(self):
        """Return speed metadata for every model with at least one response."""
        rows = self.store.fetch(
            """
            SELECT model_name, response_time, responses, output_tokens
            FROM avg_speed
            WHERE responses > 0 AND response_time > 0 AND output_tokens > 0
            """
        )
        total_time = sum(float(row["response_time"]) for row in rows)
        total_tokens = sum(int(row["output_tokens"]) for row in rows)
        if total_time <= 0 or total_tokens <= 0:
            return {}
        global_tokens_per_second = total_tokens / total_time
        results = {}
        for row in rows:
            responses = int(row["responses"])
            tokens_per_second = (
                int(row["output_tokens"]) / float(row["response_time"])
            )
            relative_percent = (
                tokens_per_second / global_tokens_per_second
            ) * 100
            results[row["model_name"]] = {
                "average_tokens_per_second": tokens_per_second,
                "relative_speed_percent": relative_percent,
                "speed_tier": speed_tier(relative_percent),
                "responses": responses,
            }
        return results

    def for_model(self, provider, model_name):
        """Return current metadata for one model, if samples exist."""
        return self.statistics().get(self.model_key(provider, model_name))


AVERAGE_SPEEDS = AverageSpeedRepository()
