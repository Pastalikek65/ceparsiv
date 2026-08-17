import sqlite3


def main() -> int:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE fts_check USING fts5(content)")
    except sqlite3.OperationalError:
        print("FTS5: YOK")
        return 0
    finally:
        conn.close()
    print("FTS5: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
