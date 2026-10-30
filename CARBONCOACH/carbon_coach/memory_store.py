"""
Carbon Coach Memory Store: SQLite & session-based persistence for activities,
summaries, and campus leaderboards.
"""

from __future__ import annotations
import sqlite3
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

DB_PATH = Path(__file__).parent / "carbon_coach.db"

BENCHMARKS = {
    "daily_student_target_kg": 3.5,
    "daily_indian_urban_avg_kg": 4.8,
    "daily_global_avg_kg": 12.8,
}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Activities table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        entity_name TEXT NOT NULL DEFAULT 'User',
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        emissions_kg REAL NOT NULL,
        raw_metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Campus entities & leaderboard
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campus_entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        entity_type TEXT NOT NULL, -- 'hostel' or 'department'
        residents_count INTEGER NOT NULL,
        baseline_daily_kg REAL NOT NULL,
        current_daily_kg REAL NOT NULL,
        reduction_percentage REAL NOT NULL,
        badge TEXT NOT NULL
    )
    """)

    conn.commit()

    # Seed campus leaderboard if empty
    cursor.execute("SELECT COUNT(*) as count FROM campus_entities")
    count = cursor.fetchone()["count"]
    if count == 0:
        sample_entities = [
            ("Hostel Nilgiri", "hostel", 280, 4.80, 2.85, 40.6, "🌿 Green Champion"),
            ("Hostel Vindhya", "hostel", 310, 4.90, 3.20, 34.7, "⚡ Energy Saver"),
            ("Hostel Himalaya", "hostel", 290, 5.10, 3.65, 28.4, "🚶 Active Commuter"),
            ("Hostel Aravali", "hostel", 320, 5.00, 3.90, 22.0, "♻️ Waste Reducer"),
            ("Dept of Computer Science", "department", 450, 4.60, 2.95, 35.8, "💻 Solar Powered Lab"),
            ("Dept of Electrical Eng", "department", 380, 4.75, 3.10, 34.7, "💡 Smart Metered"),
            ("Dept of Mechanical Eng", "department", 420, 5.20, 4.10, 21.1, "🔧 Efficiency Focused")
        ]
        cursor.executemany("""
        INSERT INTO campus_entities 
        (name, entity_type, residents_count, baseline_daily_kg, current_daily_kg, reduction_percentage, badge)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sample_entities)
        conn.commit()

    conn.close()


init_db()


class ActivityMemoryStore:
    """Manages conversational session logs and aggregated summaries."""

    @staticmethod
    def log_activity(
        session_id: str,
        category: str,
        description: str,
        emissions_kg: float,
        metadata: Optional[Dict[str, Any]] = None,
        entity_name: str = "User"
    ) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
        INSERT INTO activities (session_id, entity_name, category, description, emissions_kg, raw_metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            entity_name,
            category,
            description,
            round(emissions_kg, 4),
            json.dumps(metadata or {}),
            now
        ))
        conn.commit()
        activity_id = cursor.lastrowid
        conn.close()

        return {
            "status": "success",
            "activity_id": activity_id,
            "session_id": session_id,
            "category": category,
            "description": description,
            "emissions_kg": round(emissions_kg, 4),
            "created_at": now
        }

    @staticmethod
    def get_activities(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, session_id, entity_name, category, description, emissions_kg, raw_metadata, created_at
        FROM activities
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT ?
        """, (session_id, limit))
        rows = cursor.fetchall()
        conn.close()

        result = []
        for r in rows:
            meta = {}
            if r["raw_metadata"]:
                try:
                    meta = json.loads(r["raw_metadata"])
                except Exception:
                    pass
            item = {
                "id": r["id"],
                "session_id": r["session_id"],
                "entity_name": r["entity_name"],
                "category": r["category"],
                "description": r["description"],
                "emissions_kg": r["emissions_kg"],
                "created_at": r["created_at"],
                **meta
            }
            item["metadata"] = meta
            result.append(item)
        return result

    @staticmethod
    def get_summary(session_id: str, period: str = "all_time") -> Dict[str, Any]:
        """
        Calculates category breakdown, total emissions, and benchmark comparisons.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT category, SUM(emissions_kg) as total_cat_kg, COUNT(*) as count
        FROM activities
        WHERE session_id = ?
        GROUP BY category
        """, (session_id,))
        cat_rows = cursor.fetchall()

        cursor.execute("""
        SELECT SUM(emissions_kg) as grand_total, COUNT(*) as count
        FROM activities
        WHERE session_id = ?
        """, (session_id,))
        total_row = cursor.fetchone()
        conn.close()

        grand_total = round(total_row["grand_total"] or 0.0, 4)
        total_activities = total_row["count"] or 0

        breakdown = {}
        for r in cat_rows:
            breakdown[r["category"]] = {
                "total_kg": round(r["total_cat_kg"], 4),
                "count": r["count"],
                "percentage": round((r["total_cat_kg"] / (grand_total if grand_total > 0 else 1.0)) * 100, 1)
            }

        # Benchmark comparisons
        student_target = BENCHMARKS["daily_student_target_kg"]
        indian_urban_avg = BENCHMARKS["daily_indian_urban_avg_kg"]
        global_avg = BENCHMARKS["daily_global_avg_kg"]

        diff_from_target = round(grand_total - student_target, 2)
        status_eval = "On Track 🌱" if grand_total <= student_target else "Needs Action ⚠️"

        return {
            "session_id": session_id,
            "period": period,
            "total_emissions_kg_co2e": grand_total,
            "activity_count": total_activities,
            "category_breakdown": breakdown,
            "benchmarks": {
                "daily_student_target_kg": student_target,
                "daily_indian_urban_avg_kg": indian_urban_avg,
                "daily_global_avg_kg": global_avg,
                "current_vs_target_kg": diff_from_target,
                "status": status_eval
            }
        }

    @staticmethod
    def get_campus_leaderboard() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, name, entity_type, residents_count, baseline_daily_kg, current_daily_kg, reduction_percentage, badge
        FROM campus_entities
        ORDER BY current_daily_kg ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        leaderboard = []
        for rank, r in enumerate(rows, start=1):
            leaderboard.append({
                "rank": rank,
                "name": r["name"],
                "type": r["entity_type"].capitalize(),
                "residents": r["residents_count"],
                "baseline_daily_kg": r["baseline_daily_kg"],
                "current_daily_kg": r["current_daily_kg"],
                "reduction_percentage": r["reduction_percentage"],
                "badge": r["badge"]
            })
        return leaderboard
