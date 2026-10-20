"""
Siapkan database: buat semua tabel dan akun demo.

    python seed.py

Isi datanya dimuat terpisah oleh ETL:
    python etl_lokal.py          (skrip Python, cadangan)
    atau transformasi Pentaho    (lihat SKEMA_DATA.md)
"""
from werkzeug.security import generate_password_hash

import db


def seed_user():
    if not db.query("SELECT id FROM users WHERE username = ?", ("admin",)):
        db.execute("INSERT INTO users (username, nama, password_hash) VALUES (?, ?, ?)",
                   ("admin", "Admin Kelompok", generate_password_hash("energi2024")))
        print("Akun demo dibuat: admin / energi2024")
    else:
        print("Akun demo sudah ada: admin")


if __name__ == "__main__":
    db.init_schema()
    print("Tabel siap.")
    seed_user()
