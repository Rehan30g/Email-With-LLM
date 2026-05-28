import sqlite3
import os

# Skrip mini buat ngereset status email bos (rehanchristian30@gmail.com) aja.
# Aku sering pake ini pas lagi ngetes ulang percakapan seleksi dari awal biar gak usah nge-clear seluruh isi database.
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "agent_state.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
# Aku cuma ngehapus baris email ini biar dia bisa daftar lagi kayak user baru
cursor.execute("DELETE FROM senders WHERE email = 'rehanchristian30@gmail.com'")
conn.commit()
print("SUKSES: Status dan riwayat email 'rehanchristian30@gmail.com' berhasil aku hapus biar bersih kembali.")
conn.close()
