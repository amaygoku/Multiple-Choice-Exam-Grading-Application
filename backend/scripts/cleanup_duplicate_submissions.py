from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[2] / "backend.db"


def backup_database() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.with_name(f"{DB_PATH.stem}.backup_{stamp}{DB_PATH.suffix}")
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    backup_path = backup_database()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    deleted_ids: list[int] = []
    normalized_count = 0

    try:
        with conn:
            groups = conn.execute(
                """
                select class_id, exam_id, detected_mssv
                from submissions
                where trim(coalesce(detected_mssv, '')) <> ''
                group by class_id, exam_id, detected_mssv
                having count(*) > 1
                """
            ).fetchall()

            for group in groups:
                rows = conn.execute(
                    """
                    select *
                    from submissions
                    where class_id = ? and exam_id = ? and detected_mssv = ?
                    order by datetime(updated_at) desc, id desc
                    """,
                    (group["class_id"], group["exam_id"], group["detected_mssv"]),
                ).fetchall()
                if not rows:
                    continue

                keep = rows[0]
                student = conn.execute(
                    """
                    select id
                    from students
                    where class_id = ? and mssv = ?
                    order by id desc
                    limit 1
                    """,
                    (keep["class_id"], keep["detected_mssv"]),
                ).fetchone()
                resolved_student_id = student["id"] if student else None

                if keep["student_id"] != resolved_student_id:
                    conn.execute(
                        "update submissions set student_id = ?, updated_at = current_timestamp where id = ?",
                        (resolved_student_id, keep["id"]),
                    )
                    normalized_count += 1

                stale_ids = [row["id"] for row in rows[1:]]
                if stale_ids:
                    placeholders = ",".join("?" for _ in stale_ids)
                    conn.execute(f"delete from submissions where id in ({placeholders})", stale_ids)
                    deleted_ids.extend(stale_ids)

            singles = conn.execute(
                """
                select s.id, s.class_id, s.detected_mssv, s.student_id, st.id as resolved_student_id
                from submissions s
                left join students st
                  on st.class_id = s.class_id and st.mssv = s.detected_mssv
                where trim(coalesce(s.detected_mssv, '')) <> ''
                """
            ).fetchall()
            for row in singles:
                if row["student_id"] != row["resolved_student_id"]:
                    conn.execute(
                        "update submissions set student_id = ?, updated_at = current_timestamp where id = ?",
                        (row["resolved_student_id"], row["id"]),
                    )
                    normalized_count += 1
    finally:
        conn.close()

    print(f"Backup: {backup_path}")
    print(f"Deleted duplicate submissions: {len(deleted_ids)}")
    print(f"Normalized student_id fields: {normalized_count}")
    if deleted_ids:
        print("Deleted IDs:", ",".join(str(item) for item in deleted_ids))


if __name__ == "__main__":
    main()
