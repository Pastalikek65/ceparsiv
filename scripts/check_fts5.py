import sqlite3


def main() -> int:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE fts_check USING fts5(content)")
    except sqlite3.OperationalError:
        print("FTS5: YOK (LIKE fallback kullanilacak)")
        return 0
    print(f"FTS5: OK (sqlite {sqlite3.sqlite_version})")
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE trigram_check USING fts5(x, tokenize='trigram case_sensitive 0')"
        )
        print("Trigram tokenizer: OK (alt dize ve Turkce arama etkin)")
    except sqlite3.OperationalError:
        print("Trigram tokenizer: YOK (unicode61 kullanilacak)")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
