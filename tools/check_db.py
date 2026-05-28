import sqlite3
import json
import os

# Skrip iseng-iseng buat nge-cek data di database SQLite lokal.
# Soalnya aku sering bingung status si email rehanchristian30@gmail.com lagi apa pas ngetes kirim-kiriman.
# Aku arahin DB_PATH ke folder 'src' karena file database-nya ditaruh di sana biar root rapi.
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "agent_state.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row  # Ini biar datanya gampang dibaca kayak dictonary Python biasa
row = conn.execute("SELECT * FROM senders WHERE email = 'rehanchristian30@gmail.com'").fetchone()

if row:
    print("=== DATA AKUN rehanchristian30@gmail.com DI DATABASE ===")
    data = dict(row)
    print("Email Pengirim:", data['email'])
    print("Nama Panggilan:", data['name'])
    print("WA Number (Legacy):", data.get('wa_number'))
    print("Tujuan Pengiriman:", data.get('purpose'))
    print("Umur Pengirim:", data['age'])
    print("Status Kelulusan:", data['status'])
    print("Info Tantangan Fisik:", data['challenge_text'])
    print("Histori Chat Sama AI:")
    # Histori chat-nya aku rapiin print-nya biar enak dibaca pas debugging
    print(json.dumps(json.loads(data['history']), indent=2))
else:
    print("Yah, gak nemu data email rehanchristian30@gmail.com di database!")
conn.close()
