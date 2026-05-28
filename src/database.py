import sqlite3
import json
import os

# Database ini aku pake sqlite3 bawaan Python biar gampang, gak usah install database mysql/postgres segala.
# Aku sempet pusing kalau disuruh install server database luar pas pertama kali belajar.
# File database 'agent_state.db' bakal otomatis dibuat di dalam folder 'src' pas pertama kali program dijalanin.
# Ajaib banget sih, kok bisa ya otomatis ke-create sendiri!
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_state.db")

class AgentDatabase:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self):
        # Kata ChatGPT, biasakan bikin fungsi khusus koneksi biar gak capek ngetik berulang-ulang
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Ini biar datanya bisa dibaca kayak dictionary, asik banget!
        return conn

    def init_db(self):
        """Menginisialisasi tabel database jika belum ada."""
        with self._get_connection() as conn:
            # Di sini aku buat tabel namanya 'senders' buat nyimpen status seleksi kandidat
            # Kata tutorial di internet, PRIMARY KEY itu wajib unik biar gak ada email kembar yang bikin pusing
            conn.execute("""
                CREATE TABLE IF NOT EXISTS senders (
                    email TEXT PRIMARY KEY,
                    name TEXT,
                    wa_number TEXT,
                    purpose TEXT,
                    age INTEGER,
                    status TEXT DEFAULT 'PENDING_DETAILS',
                    challenge_text TEXT,
                    history TEXT DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(senders)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'purpose' not in columns:
                try:
                    conn.execute("ALTER TABLE senders ADD COLUMN purpose TEXT")
                    print("[Database] Asyik! Kolom 'purpose' berhasil ditambahkan ke tabel senders.")
                except Exception as e:
                    print(f"[Database Error] Yah, gagal nambahin kolom 'purpose': {e}")
            
            conn.commit()

    def get_sender(self, email_address):
        """Mendapatkan data pengirim berdasarkan alamat email."""
        email_address = email_address.strip().lower()  # Aku lowercase biar gak sensitif huruf besar kecil
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM senders WHERE email = ?", (email_address,)
            ).fetchone()
            
            if row:
                # Karena sqlite gak bisa nyimpen list/array, aku simpannya jadi teks (JSON string).
                # Nah, pas dibaca, aku ubah lagi jadi list asli Python biar bisa dipakai sama AI Agent.
                data = dict(row)
                data['history'] = json.loads(data['history'])
                return data
            return None

    def create_sender(self, email_address):
        """Membuat entri pengirim baru jika belum ada."""
        email_address = email_address.strip().lower()
        with self._get_connection() as conn:
            # INSERT OR IGNORE biar gak error kalau datanya udah pernah didaftarin sebelumnya
            conn.execute(
                "INSERT OR IGNORE INTO senders (email, history) VALUES (?, '[]')",
                (email_address,)
            )
            conn.commit()
        return self.get_sender(email_address)

    def save_sender(self, email_address, name=None, wa_number=None, purpose=None, age=None, status=None, challenge_text=None, history=None):
        """Memperbarui data pengirim."""
        email_address = email_address.strip().lower()
        
        # Ambil data lama dulu biar kalau parameter barunya None (gak diisi), datanya gak hilang/tertimpa kosong
        current = self.get_sender(email_address)
        if not current:
            current = self.create_sender(email_address)

        # Logika OR di bawah ini aku copas dari StackOverflow biar tetep pake nilai lama kalau nilai barunya kosong
        name = name if name is not None else current['name']
        wa_number = wa_number if wa_number is not None else current['wa_number']
        purpose = purpose if purpose is not None else current.get('purpose')
        age = age if age is not None else current['age']
        status = status if status is not None else current['status']
        challenge_text = challenge_text if challenge_text is not None else current['challenge_text']
        
        if history is not None:
            history_str = json.dumps(history)
        else:
            history_str = json.dumps(current['history'])

        # Query UPDATE buat nyimpen data seleksi terbaru
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE senders 
                SET name = ?, wa_number = ?, purpose = ?, age = ?, status = ?, challenge_text = ?, history = ?, updated_at = CURRENT_TIMESTAMP
                WHERE email = ?
            """, (name, wa_number, purpose, age, status, challenge_text, history_str, email_address))
            conn.commit()

    def delete_sender(self, email_address):
        """Menghapus data pengirim (jika diperlukan untuk reset)."""
        # Ini buat ngetes doang sih kalau aku pengen reset status email tertentu
        email_address = email_address.strip().lower()
        with self._get_connection() as conn:
            conn.execute("DELETE FROM senders WHERE email = ?", (email_address,))
            conn.commit()
