import os
import sys
import time

# Model AI yang di pakai untuk baca, balas email, dan pengambil keputusan adalah Deepseek v4 Flash, Karena Kualitas tinggi di harga murah.
# Aku tambahin baris ini karena ChatGPT bilang biar gak kena error 'ModuleNotFoundError' pas di-run
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from dotenv import load_dotenv
from database import AgentDatabase
from agent_core import HanzkuAgent
from email_service import EmailService

# PENTING: apa ya?
# mksh buat "kootenpv/yagmail" yang ngasih tutor cara kirim email
load_dotenv()

def run_agent():
    print("=" * 60)
    print("      === HANZKU.MY.ID ===      ")
    print("      Vibe Coded by @Rehan30g on Github")
    print("=" * 60)
    
    try:
        # cek semua komponen utama
        db = AgentDatabase()
        agent = HanzkuAgent()
        email_svc = EmailService()
        print("[Sistem] yey! Database, AI Agent, sama Email Service berhasil nyala.")
    except Exception as e:
        print(f"[Fatal Error] agal pas nge-muat sistemnya: {e}")
        print("Plenger, lu ga atur apikey di .env dulu?.")
        sys.exit(1)

    print("\n[Sistem] Hello World")
    print("[Sistem] Menunggu email dikirim ke support@hanzku.my.id...")
    print("-" * 60)

    polling_interval = 10  # Cek setiap 10 detik sekali (biar gak kena limit Gmail)

    while True:
        try:
            # 1. Ambil email yang belum dibaca dari Gmail  (masih pake Yagmail btw)
            new_emails = email_svc.fetch_unseen_emails()
            
            # 2. Proses satu-satu emailnya
            for mail_data in new_emails:
                print(f"\n[Email Baru] email baru dari: {mail_data['sender_name']} <{mail_data['sender_email']}>")
                print(f"[Email Baru] Subjek: {mail_data['subject']}")
                
                # Semua logika ribet di tulis AI (analisis DeepSeek, update DB, kirim balasan, Google Sheets)
                # udah aku pindahin ke dalam file agent_core.py pake bantuan refactoring tool.
                agent.process_incoming_email(mail_data, db, email_svc)
                
                print("-" * 60)

        # Ctrl+C
        except KeyboardInterrupt:
            print("\n[Sistem] Kamu pencet Ctrl+C, jadi botnya mati ya.")
            break
        except Exception as e:
            print(f"[Error] ada error di loop utama: {e}")
            
        # Kasih jeda waktu sebelum ngecek Gmail lagi
        time.sleep(polling_interval)

if __name__ == "__main__":
    run_agent()
