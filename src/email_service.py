import os
import imaplib
import email
from email.utils import parseaddr
import requests
from dotenv import load_dotenv

# Aku load file .env biar kredensial kayak API key gak bocor pas di-push ke GitHub
load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

class EmailService:
    def __init__(self):
        self.gmail_user = GMAIL_USER
        self.gmail_password = GMAIL_APP_PASSWORD
        self.resend_key = RESEND_API_KEY
        
        self.google_sheet_url = os.getenv("GOOGLE_SHEET_URL")
        
        # Variabel di bawah ini buat bantu stacked logging biar terminalnya gak spamming
        self.last_log = None
        self.dup_count = 1
        
        if not self.gmail_user or not self.gmail_password:
            # Aku taruh ini biar langsung sadar kalau lupa ngisi email/password di .env
            raise ValueError("Waduh! Gmail credentials (GMAIL_USER/GMAIL_APP_PASSWORD) belum kamu isi di .env!")
        if not self.resend_key:
            raise ValueError("Kunci RESEND_API_KEY belum kamu pasang di .env!")

    def log_stacked(self, message):
        """Mencetak log bertumpuk (stack) pada baris yang sama untuk menghindari spam terminal."""
        # Fungsi keren ini diajarin sama ChatGPT biar log terminalnya rapi di satu baris pake \r
        import sys
        if message == self.last_log:
            self.dup_count += 1
            sys.stdout.write(f"\r{message} [{self.dup_count}x]")
            sys.stdout.flush()
        else:
            if self.last_log is not None:
                sys.stdout.write("\n")
            self.last_log = message
            self.dup_count = 1
            sys.stdout.write(message)
            sys.stdout.flush()

    def fetch_unseen_emails(self):
        """Membaca email belum terbaca dari Gmail, mengembalikan list email terurai."""
        # Bagian baca email dari Gmail ini pusing banget ya ampun!
        # Aku bingung cara konek pake protokol IMAP.
        # Untung dikasih contoh script di stackoverflow!
        # Sumber: stackoverflow.com/questions/4214713/how-to-read-email-attachments-in-python
        unseen_emails = []
        try:
            # Hubungkan ke Gmail IMAP lewat SSL di port 993 (kata tutorial ini wajib aman)
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(self.gmail_user, self.gmail_password)
            mail.select("inbox")

            # Cari email yang statusnya masih belum dibaca (UNSEEN)
            status, response = mail.search(None, "UNSEEN")
            if status != "OK":
                return []

            email_ids = response[0].split()
            msg = f"[IMAP] Ditemukan {len(email_ids)} email baru belum terbaca."
            
            # Kalau gak ada email baru, aku print pake stacked log biar gak ngebenuhin terminal
            if len(email_ids) == 0:
                self.log_stacked(msg)
            else:
                if self.last_log is not None:
                    import sys
                    sys.stdout.write("\n")
                    self.last_log = None
                print(msg)

            for e_id in email_ids:
                status, data = mail.fetch(e_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Parse data header pengirim dan subjek
                from_header = msg.get("From", "")
                name, email_address = parseaddr(from_header)
                subject = msg.get("Subject", "No Subject")
                message_id = msg.get("Message-ID", "")

                body = ""
                image_attachments = []
                
                # Email ada yang teks biasa, ada yang html, ada juga yang ngirim berkas lampiran gambar.
                # Codingannya jadi ribet banget, untung dibantuin ChatGPT nulis loop parsing attachment ini.
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))

                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            try:
                                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            except Exception:
                                pass
                        elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                            try:
                                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            except Exception:
                                pass
                        elif part.get_content_maintype() == 'image' or "image/" in content_type:
                            try:
                                file_data = part.get_payload(decode=True)
                                if file_data:
                                    import time
                                    import base64
                                    filename = part.get_filename() or f"image_{int(time.time())}.jpg"
                                    # Di sini aku taruh folder download-an gambar ke dalam subfolder 'src/files'
                                    # biar gak ngotori root folder pas aku push ke GitHub.
                                    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "files"), exist_ok=True)
                                    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files", filename)
                                    with open(filepath, "wb") as f:
                                        f.write(file_data)
                                    
                                    # Gambar aku ubah ke base64 biar bisa dikirim gampang lewat API internet ke Gemini
                                    data_base64 = base64.b64encode(file_data).decode('utf-8')
                                    image_attachments.append({
                                        "filename": filename,
                                        "filepath": filepath,
                                        "data_base64": data_base64,
                                        "mime_type": content_type
                                    })
                                    print(f"[IMAP] Keren! Berhasil download lampiran gambar: {filename}")
                            except Exception as e:
                                print(f"[IMAP Error] Gagal download attachment gambarnya: {e}")
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                body = body.strip() if body else ""

                unseen_emails.append({
                    "id": e_id,
                    "sender_name": name,
                    "sender_email": email_address.strip().lower(),
                    "subject": subject,
                    "message_id": message_id,
                    "body": body,
                    "images": image_attachments
                })

            mail.logout()
        except Exception as e:
            print(f"[IMAP Error] Haduh, gagal baca email dari Gmail: {e}")
        
        return unseen_emails

    def _markdown_to_html(self, text):
        """Mengonversi Markdown sederhana (bold, lists, linebreaks) menjadi HTML yang didukung email client."""
        # Karena respon dari AI Agent itu isinya teks biasa dengan format Markdown (seperti **tebal** atau poin list),
        # sedang pas ngirim email kita butuh format HTML biar keliatan rapi, 
        # jadi di bawah ini aku bikin konverter regex sederhana buatan sendiri (dengan bantuan AI juga sih wkwk).
        import re
        
        # 1. Bersihkan tanda tanya aneh dari encoding bermasalah
        text = text.replace("\ufffd", " - ")

        # 2. Tebalkan tulisan: **teks** -> <strong>teks</strong>
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

        # 3. Parsing format daftar (List Poin dan Nomor)
        lines = text.split('\n')
        in_list = False
        in_num_list = False
        html_lines = []

        for line in lines:
            stripped = line.strip()
            # Poin (- atau *)
            if re.match(r'^[\-\*]\s+(.*)', stripped):
                content = re.sub(r'^[\-\*]\s+', '', stripped)
                if not in_list:
                    html_lines.append('<ul style="margin: 5px 0; padding-left: 20px;">')
                    in_list = True
                html_lines.append(f'<li style="margin-bottom: 5px;">{content}</li>')
            # Nomor (1. atau 2.)
            elif re.match(r'^\d+\.\s+(.*)', stripped):
                content = re.sub(r'^\d+\.\s+', '', stripped)
                if not in_num_list:
                    html_lines.append('<ol style="margin: 5px 0; padding-left: 20px;">')
                    in_num_list = True
                html_lines.append(f'<li style="margin-bottom: 5px;">{content}</li>')
            else:
                # Tutup list tag kalau ketemu baris teks biasa
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                if in_num_list:
                    html_lines.append('</ol>')
                    in_num_list = False
                html_lines.append(line)

        # Tutup sisa list yang menggantung
        if in_list:
            html_lines.append('</ul>')
        if in_num_list:
            html_lines.append('</ol>')

        # Gabungkan barisnya dan ganti \n dengan breakline HTML <br>
        html_content = ""
        for line in html_lines:
            if line.startswith('<ul') or line.startswith('</ul') or line.startswith('<ol') or line.startswith('</ol') or line.startswith('<li'):
                html_content += line + "\n"
            else:
                html_content += line + "<br>\n"

        # Bungkus dengan inline CSS biar layout emailnya keliatan modern dan elegan pas dibuka
        styled_html = f"""
        <div style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; color: #1e293b; line-height: 1.6; max-width: 600px;">
            {html_content}
        </div>
        """
        return styled_html

    def send_reply(self, to_email, subject, body_text, original_message_id=None):
        """Mengirim email balasan menggunakan Resend API."""
        # Tutorial Resend API aku contek dari web dokumentasi resend.com langsung!
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {self.resend_key}",
            "Content-Type": "application/json"
        }

        # Subjek email dibalas otomatis dikasih awalan "Re:" biar nyambung di Gmail pengirim
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Setup header threading biar emailnya numpuk rapi di satu chat yang sama (tidak bikin email thread baru)
        email_headers = {}
        if original_message_id:
            email_headers["In-Reply-To"] = original_message_id
            email_headers["References"] = original_message_id

        # Konversi markdown dari AI ke HTML agar render sempurna
        html_body = self._markdown_to_html(body_text)

        # Payload kirim email Resend.
        # Oh iya, reply_to aku arahin ke support@hanzku.my.id biar kalau user klik 'Balas', 
        # emailnya otomatis masuk kembali ke server IMAP aku. Cerdas kan idenya? wkwk
        payload = {
            "from": "Hanzku Support <gatekeeper@support.hanzku.my.id>",
            "to": to_email,
            "subject": subject,
            "text": body_text,
            "html": html_body,
            "reply_to": "support@hanzku.my.id",
            "headers": email_headers
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            print(f"[Resend] Mantap! Berhasil kirim balasan otomatis ke {to_email}")
            return True
        except Exception as e:
            print(f"[Resend Error] Duh gagal kirim balasan ke {to_email}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Detail eror resend: {e.response.text}")
            return False

    def mask_email(self, email_address):
        """Menyensor alamat email: menampilkan 2 karakter pertama dan domain setelah @, bintang tepat 4."""
        # Aku sensor emailnya demi privasi keamanan, biar email kandidat gak langsung keliatan di laporan
        if not email_address or "@" not in email_address:
            return email_address
        parts = email_address.split("@", 1)
        username = parts[0]
        domain = parts[1]
        
        prefix = username[:2]
        return f"{prefix}****@{domain}"

    def send_approval_report(self, sender_data, original_subject):
        """Mengirimkan laporan persetujuan HTML premium ke Rehanchristian30@gmail.com dengan data tersensor."""
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {self.resend_key}",
            "Content-Type": "application/json"
        }

        masked_email = self.mask_email(sender_data.get('email', ''))
        purpose_text = sender_data.get('purpose', 'Tidak terdeteksi')

        # Ini generate gelembung chat (chat bubble) obrolan AI biar keliatan kayak aplikasi chatting modern
        chat_html = ""
        for msg in sender_data.get('history', []):
            role = msg.get('role', 'user')
            content = msg.get('content', '').replace('\n', '<br>')
            
            if role == 'user':
                chat_html += f"""
                <div style="margin-bottom: 15px; text-align: right;">
                    <div style="display: inline-block; padding: 10px 14px; border-radius: 12px 12px 0 12px; background-color: #2e3a59; color: #ffffff; max-width: 80%; text-align: left; font-size: 14px; border: 1px solid #3f51b5;">
                        <strong style="color: #8fa4f9; font-size: 11px; display: block; margin-bottom: 4px;">PENGIRIM</strong>
                        {content}
                    </div>
                </div>
                """
            else:
                chat_html += f"""
                <div style="margin-bottom: 15px; text-align: left;">
                    <div style="display: inline-block; padding: 10px 14px; border-radius: 12px 12px 12px 0; background-color: #1e1e24; color: #e0e0e6; max-width: 80%; text-align: left; font-size: 14px; border: 1px solid #ff4081;">
                        <strong style="color: #ff80ab; font-size: 11px; display: block; margin-bottom: 4px;">AI GATEKEEPER Council</strong>
                        {content}
                    </div>
                </div>
                """

        # Desain laporan premium khusus dark mode futuristik.
        # Bos Rehan kan suka banget sama gaya-gaya dark mode neon cyber gitu wkwk, jadi aku bikin desain ini biar dia seneng.
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Laporan Kelulusan AI Gatekeeper</title>
            <style>
                body {{
                    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    background-color: #0d0e12;
                    color: #e2e8f0;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 30px auto;
                    background: linear-gradient(145deg, #11131c, #0a0b0f);
                    border-radius: 16px;
                    border: 1px solid #222533;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(90deg, #7c4dff, #ff4081);
                    padding: 24px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 20px;
                    color: #ffffff;
                    text-transform: uppercase;
                    letter-spacing: 1.5px;
                }}
                .header p {{
                    margin: 5px 0 0 0;
                    font-size: 12px;
                    color: #e0d4ff;
                }}
                .content {{
                    padding: 24px;
                }}
                .card {{
                    background-color: #151824;
                    border-radius: 12px;
                    border: 1px solid #22263b;
                    padding: 18px;
                    margin-bottom: 20px;
                }}
                .card-title {{
                    font-size: 14px;
                    font-weight: 700;
                    color: #ff4081;
                    text-transform: uppercase;
                    margin-top: 0;
                    margin-bottom: 12px;
                    letter-spacing: 0.8px;
                    border-bottom: 1px solid #22263b;
                    padding-bottom: 6px;
                }}
                .info-row {{
                    display: flex;
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                .info-label {{
                    width: 100px;
                    color: #707593;
                    font-weight: 600;
                }}
                .info-value {{
                    flex: 1;
                    color: #f8fafc;
                }}
                .badge {{
                    display: inline-block;
                    padding: 4px 8px;
                    background-color: #00e676;
                    color: #000000;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 4px;
                    text-transform: uppercase;
                }}
                .chat-box {{
                    background-color: #0b0c10;
                    border-radius: 8px;
                    padding: 15px;
                    border: 1px solid #1a1c24;
                    max-height: 400px;
                    overflow-y: auto;
                }}
                .footer {{
                    background-color: #090a0d;
                    padding: 16px;
                    text-align: center;
                    font-size: 11px;
                    color: #525876;
                    border-top: 1px solid #181921;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Seseorang Berhasil Menembus Seleksi!</h1>
                    <p>Hanzku Keren • hanzku.my.id</p>
                </div>
                
                <div class="content">
                    <div class="card">
                        <h3 class="card-title">Profil Pengirim</h3>
                        <div class="info-row">
                            <span class="info-label">Nama Singkat</span>
                            <span class="info-value"><strong>{sender_data.get('name')}</strong></span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Email</span>
                            <span class="info-value"><code>{masked_email}</code></span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Umur</span>
                            <span class="info-value">{sender_data.get('age')} Tahun</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Tujuan</span>
                            <span class="info-value" style="color: #00e676; font-weight: bold;">{purpose_text}</span>
                        </div>
                        <div class="info-row" style="margin-top: 10px;">
                            <span class="info-label">Status</span>
                            <span class="info-value"><span class="badge">PASSED</span></span>
                        </div>
                    </div>

                    <div class="card">
                        <h3 class="card-title">Tantangan Verifikasi Fisik</h3>
                        <p style="margin: 0; font-size: 14px; color: #b0b3c6; font-style: italic;">
                            "{sender_data.get('challenge_text')}"
                        </p>
                    </div>

                    <div class="card" style="margin-bottom: 0;">
                        <h3 class="card-title">Transkrip Enkripsi Percakapan</h3>
                        <div class="chat-box">
                            {chat_html}
                        </div>
                    </div>
                </div>
                
                <div class="footer">
                    Pesan ini dihasilkan secara otomatis oleh Dewan Penjaga Hanzku Support.<br>
                    © 2026 hanzku.my.id. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

        payload = {
            "from": "Hanzku Support Council <gatekeeper@support.hanzku.my.id>",
            "to": "Rehanchristian30@gmail.com", # Bos Rehan!
            "subject": f"✨ [Lolos Seleksi] {sender_data.get('name')} - {original_subject}",
            "html": html_content
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            print(f"[Resend] Laporan kelulusan HTML Premium berhasil meluncur ke email bos Rehan!")
            return True
        except Exception as e:
            print(f"[Resend Error] Haduh gagal ngirim laporan kelulusan: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Detail Eror Laporan: {e.response.text}")
            return False

    def send_to_google_sheet(self, sender_data):
        """Mengirim data peserta yang lolos seleksi ke Google Spreadsheet via Apps Script Web App (Email Tersensor)."""
        if not self.google_sheet_url:
            print("[Google Sheets] Wah, setoran dilewati karena GOOGLE_SHEET_URL belum dipasang di .env!")
            return False

        masked_email = self.mask_email(sender_data.get("email"))

        payload = {
            "name": sender_data.get("name"),
            "email": masked_email,
            "wa_number": sender_data.get("purpose"),  # Backward compatibility kata ChatGPT wkwk
            "purpose": sender_data.get("purpose"),     
            "age": sender_data.get("age"),
            "challenge_text": sender_data.get("challenge_text")
        }

        try:
            print(f"[Google Sheets] Aku setor data {payload['name']} ke Google Sheet ya...")
            # Kita panggil Google Apps Script Web App pake method POST biasa
            response = requests.post(self.google_sheet_url, json=payload, timeout=15)
            response.raise_for_status()
            res_json = response.json()
            if res_json.get("status") == "success":
                print("[Google Sheets] Hore! Berhasil nyatet datanya ke Google Spreadsheet!")
                return True
            else:
                print(f"[Google Sheets Error] Yah gagal nyatet kata Google Script: {res_json.get('message')}")
                return False
        except Exception as e:
            print(f"[Google Sheets Error] Gagal konek ke Google Apps Script Web App: {e}")
            return False
