import sqlite3
import os

# Waduh! Skrip darurat ini aku pake buat ngehapus bersih SEMUA data pengirim di database.
# Jangan sampe salah jalanin pas lagi running production ya, nanti datanya ilang semua aku bisa dipecat wkwk!
# Tapi kalau lagi ngetes dari awal dari nol, ini ngebantu banget biar DB-nya bersih lagi.
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "agent_state.db")

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # DELETE FROM senders artinya hapus semua baris data di tabel senders!
    cursor.execute("DELETE FROM senders")
    conn.commit()
    print("SUCCESS: Hore! Seluruh data seleksi di database SQLite lokal berhasil aku hapus bersih!")
    conn.close()
except Exception as e:
    print(f"ERROR: Waduh gagal pas nge-clear database: {e}")
