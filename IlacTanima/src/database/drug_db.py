import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List


@dataclass
class Drug:
    name: str
    active_ingredient: str
    company: str
    barcode: str
    sgk_status: str
    dosage: str
    atc_code: str
    warnings: str
    prescription_type: str


_EMPTY = Drug('', '', '', '', '', '', '', '', '')


class DrugDatabase:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS drugs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                name              TEXT NOT NULL,
                active_ingredient TEXT DEFAULT '',
                company           TEXT DEFAULT '',
                barcode           TEXT DEFAULT '',
                sgk_status        TEXT DEFAULT 'Bilinmiyor',
                dosage            TEXT DEFAULT '',
                atc_code          TEXT DEFAULT '',
                warnings          TEXT DEFAULT '',
                prescription_type TEXT DEFAULT 'Reçeteli'
            );
            CREATE INDEX IF NOT EXISTS idx_barcode ON drugs(barcode);
            CREATE INDEX IF NOT EXISTS idx_name    ON drugs(name COLLATE NOCASE);
        """)
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM drugs").fetchone()[0]

    def insert_bulk(self, rows: List[dict]):
        self.conn.executemany("""
            INSERT OR IGNORE INTO drugs
                (name, active_ingredient, company, barcode, sgk_status,
                 dosage, atc_code, warnings, prescription_type)
            VALUES
                (:name, :active_ingredient, :company, :barcode, :sgk_status,
                 :dosage, :atc_code, :warnings, :prescription_type)
        """, rows)
        self.conn.commit()

    def search_by_barcode(self, barcode: str) -> Optional[Drug]:
        row = self.conn.execute(
            "SELECT * FROM drugs WHERE barcode = ? LIMIT 1", (barcode,)
        ).fetchone()
        return self._to_drug(row)

    def search_by_name(self, name: str) -> Optional[Drug]:
        """
        OCR çıktısından ilaç adı ara.
        Önce ilk kelimeyle LIKE araması, sonra fuzzy match.
        """
        if not name or len(name) < 2:
            return None

        first_word = name.split()[0]

        # 1. İlk kelimeyle direkt eşleşme (büyük/küçük harf yok say)
        row = self.conn.execute(
            "SELECT * FROM drugs WHERE name LIKE ? LIMIT 1",
            (f"{first_word}%",)
        ).fetchone()
        if row:
            return self._to_drug(row)

        # 2. İlk kelime tam adın içinde geçiyor mu
        row = self.conn.execute(
            "SELECT * FROM drugs WHERE name LIKE ? LIMIT 1",
            (f"%{first_word}%",)
        ).fetchone()
        if row:
            return self._to_drug(row)

        # 3. Fuzzy match — yazım hatalarını tolere et
        try:
            from rapidfuzz import process, fuzz
            rows = self.conn.execute("SELECT * FROM drugs").fetchall()
            if not rows:
                return None
            names = [r[1] for r in rows]
            # token_set_ratio: kelime sırası önemli değil, kısmi eşleşme daha iyi
            match = process.extractOne(
                name, names,
                scorer=fuzz.token_set_ratio,
                score_cutoff=45      # düşük eşik — OCR kusurlu olabilir
            )
            if match:
                return self._to_drug(rows[match[2]])
        except ImportError:
            pass
        return None

    def _to_drug(self, row) -> Optional[Drug]:
        if not row:
            return None
        return Drug(
            name=row[1], active_ingredient=row[2], company=row[3],
            barcode=row[4], sgk_status=row[5], dosage=row[6],
            atc_code=row[7], warnings=row[8], prescription_type=row[9],
        )
