import os
import json
import requests
from dotenv import load_dotenv

# Aku load file .env biar kredensialnya aman
# Tutorialnya dari repo GitHub bang 'simonw/llm-openrouter'
# Dia ngasih contoh cara paling gampang buat nembak API OpenRouter pake requests biasa.
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "deepseek/deepseek-v4-flash"  # Model AI yg aku pake buat baca,tulis email serta membuat keputusan

class HanzkuAgent:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        if not self.api_key:
            # mastiin
            raise ValueError("Aduh! Kunci OPENROUTER_API_KEY tidak ditemukan di file .env kamu!")

    def _call_openrouter(self, messages, tools=None, use_alibaba=True):
        """Memanggil API OpenRouter dengan fallback provider."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hanzku.my.id",  # Custom domain bios
            "X-Title": "Hanzku AI Gatekeeper"
        }

        # Ini body request JSON yang mau aku kirim ke OpenRouter
        payload = {
            "model": MODEL_NAME,
            "messages": messages
        }
        
        # Kalau AI-nya butuh panggil tool (misal buat verifikasi gambar), tambahin parameter tools
        if tools:
            payload["tools"] = tools
        else:
            # Kalau gak pake tools, paksa AI balikin JSON murni biar gampang diparsing pake json.loads()
            payload["response_format"] = {"type": "json_object"}

        # Tips dari bang dimas-dev-98: pake provider Alibaba biar responnya cepet banget!
        if use_alibaba:
            payload["provider"] = {
                "order": ["Alibaba"],
                "allow_fallbacks": True
            }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            res_json = response.json()
            return res_json['choices'][0]['message']
        except Exception as e:
            # Kalau Alibaba lagi down, aku coba fallback (cadangan) pake provider bebas biar sistemnya gak macet
            print(f"[OpenRouter Error] Yah, gagal pas nyoba konek lewat Alibaba: {e}")
            if use_alibaba:
                print("[OpenRouter Retry] Aku coba lagi ya pake auto routing biasa tanpa Alibaba...")
                return self._call_openrouter(messages, tools, use_alibaba=False)
            else:
                raise e

    def _call_gemini_verify_image(self, base64_image_data, mime_type="image/jpeg"):
        """Memanggil Google Gemini 2.5 Flash Lite via OpenRouter untuk verifikasi objek alam."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hanzku.my.id",
            "X-Title": "Hanzku AI Gatekeeper Image Verifier"
        }
        
        # System prompt ini aku ketik panjang-panjang dibantu ChatGPT biar Gemini-nya pinter 
        # buat ngebedain foto tanaman/daun/batu sama foto abal-abal/bot internet.
        gemini_prompt = """
        Tugas Anda adalah menganalisis gambar/foto yang diunggah oleh pengirim email dan menentukan apakah gambar tersebut menunjukkan objek sehari-hari yang biasa/dapat ditemukan di alam bebas (misalnya daun, tanaman, bunga, batu, pohon, air, awan, tanah, serangga, burung, ranting, dll.).
        
        Harap kembalikan respons Anda dalam format JSON dengan struktur berikut:
        {
          "is_nature_object": true atau false,
          "explanation": "Penjelasan singkat dalam bahasa Indonesia mengenai objek apa yang ada di gambar dan mengapa objek tersebut termasuk atau tidak termasuk objek alam sehari-hari.",
          "object_name": "Satu kata benda tunggal kapital dalam bahasa Indonesia yang menggambarkan objek utama alam dalam foto (contoh: 'Daun', 'Batu', 'Bunga', 'Pohon', 'Air', 'Serangga'). Jika tidak valid atau bukan objek alam bebas, isi dengan null."
        }
        """
        
        # Di sini aku kirim gambar base64-nya langsung ke Gemini lewat OpenRouter. 
        # Awalnya aku bingung caranya, untung diajarin AI!
        payload = {
            "model": "google/gemini-2.5-flash-lite",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": gemini_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image_data}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            print(f"[Gemini Verification Raw]: {content}")
            return content
        except Exception as e:
            print(f"[Gemini Error] Waduh, Gemini-nya lagi ngadat pas nge-cek gambar: {e}")
            return json.dumps({
                "is_nature_object": False,
                "explanation": f"Gagal memproses gambar karena gangguan sistem: {str(e)}"
            })

    def process_message(self, sender_email, new_message, current_state, image_attachments=None):
        """
        Memproses pesan email masuk dari pengirim menggunakan LLM dan mengembalikan state baru.
        """
        history = current_state.get('history', [])
        status = current_state.get('status', 'PENDING_DETAILS')
        name = current_state.get('name')
        purpose = current_state.get('purpose')
        age = current_state.get('age')
        challenge_text = current_state.get('challenge_text')

        # Kalau ada email baru masuk, tambahin ke histori obrolan biar AI-nya inget konteks obrolan sebelumnya
        if new_message:
            history.append({"role": "user", "content": new_message})

        # Kalau user ngirim gambar di emailnya
        has_image = image_attachments and len(image_attachments) > 0
        if has_image:
            image_note = f"\n\n[SISTEM NOTE: Pengirim melampirkan sebuah berkas gambar/foto. Silakan panggil tool 'verify_nature_image' untuk menganalisis dan memverifikasi gambar tersebut menggunakan Gemini 2.5 Flash Lite.]"
            if history and history[-1]["role"] == "user":
                history[-1]["content"] += image_note

        # System prompt super duper ketat! Bos Rehan minta bahasanya formal korporasi kayak surat dinas resmi, 
        # dan PENTING: DILARANG nyebut nama asli bos Rehan! 
        # Aku sempet dimarahin gara-gara hampir bocorin namanya. Jadi aku tulis aturan ini tebel-tebel biar AI-nya patuh.
        system_prompt = f"""
Anda adalah AI Agent Penyeleksi Profesional (Hanzku Executive Support) yang bertindak sebagai Asisten Administrasi untuk Pemilik hanzku.my.id (Pimpinan kami).
Tugas Anda adalah memproses dan menyeleksi setiap permohonan/email yang dikirimkan ke support@hanzku.my.id sebelum dapat diteruskan langsung ke Pimpinan kami.

SANGAT KRITIS / DILARANG KERAS:
- Jangan pernah menyebut nama asli Pimpinan kami ("Rehan Christian" or "Rehan") kepada pengirim. Selalu sebut beliau dengan panggilan "Pimpinan kami" atau "Pemilik hanzku.my.id". Beliau adalah individu dengan privasi tingkat tinggi, sehingga identitas asli beliau dilindungi secara administratif.
- Posisikan diri Anda sebagai asisten administrasi eksekutif profesional yang sangat formal, sopan, elegan, berwibawa, namun tetap tegas dan selektif.

ATURAN GAYA TULISAN - BASA-BASI SUPER FORMAL KANTORAN:
- Gunakan bahasa korespondensi bisnis korporat yang sangat formal, kaya akan kalimat pembuka, kalimat transisi bisnis, basa-basi profesional yang sopan, dan kalimat penutup bisnis yang elegan.
- **DILARANG KERAS** menulis email yang terlalu singkat, gersang, atau tidak sopan. Gunakan kalimat formal panjang khas surat dinas korporasi (seperti: "Menindaklanjuti email yang Anda kirimkan...", "Sebelum kami dapat meneruskan berkas permohonan Bapak/Ibu...", "Kami sangat menghargai minat dan perhatian yang Bapak/Ibu berikan...", "Demikian pemberitahuan administratif ini kami sampaikan, atas perhatian dan kerja sama Bapak/Ibu kami ucapkan terima kasih.").
- **DILARANG KERAS** menjelaskan contoh atau memberikan keterangan tambahan di dalam tanda kurung pada daftar persyaratan utama. Keterangan persyaratan wajib disajikan secara bersih, to-the-point, tanpa penjelasan tambahan di sampingnya.
- Tulis daftar data kelayakan kelengkapan berkas **wajib persis seperti ini, tanpa kurung penjelasan apa pun**:
  1. Nama Singkat
  2. Umur
  3. Tujuan
- Seluruh basa-basi bisnis harus diletakkan pada paragraf pembuka dan paragraf penutup email, bukan di dalam daftar persyaratan itu sendiri.

STATUS SAAT INI:
- Nama Singkat Terdeteksi: {name or 'Belum ada'}
- Umur Terdeteksi: {age or 'Belum ada'}
- Tujuan Terdeteksi: {purpose or 'Belum ada'}
- Status Seleksi: {status}
- Hasil Verifikasi Foto Sebelumnya: {challenge_text or 'Belum diberikan'}

ATURAN PROSES SELEKSI:
1. Jika salah satu dari 3 kriteria kelayakan utama (Nama Singkat, Umur, Tujuan) belum lengkap, tulislah email bisnis formal yang panjang, sopan, dan penuh basa-basi korporat untuk memohon kelengkapan data-data tersebut. Status tetap "PENDING_DETAILS".
2. Jika data (Nama Singkat, Umur, Tujuan) sudah lengkap, JANGAN langsung meloloskan pengirim. Anda diwajibkan untuk menjalankan Verifikasi Keaslian Pengirim (Human Authenticity Verification).
   - Tulis surat bisnis formal yang sangat sopan untuk menginstruksikan mereka membalas email dengan melampirkan **satu buah foto/gambar objek alam bebas** (seperti daun, batu, atau tanaman) untuk tahap verifikasi akhir demi menyaring bot otomatis.
   - Buat instruksi verifikasi foto ini terdengar sangat profesional dan penting dengan kalimat bisnis yang rapi, namun daftar filenya tetap bersih.
   - Ubah status menjadi "CHALLENGING". Pada field "challenge_text", Anda WAJIB menuliskan `"Verifikasi objek alam bebas dengan mengirimkan foto"` sebagai penanda awal berkas belum masuk.
3. Jika status saat ini adalah "CHALLENGING":
   - Jika pengirim menyertakan gambar, Anda HARUS memanggil tool/fungsi `verify_nature_image` untuk menganalisis berkas tersebut.
   - Evaluasi nilai JSON "is_nature_object" hasil dari tool tersebut secara ketat:
     - Jika "is_nature_object" bernilai true:
       - Ubah status menjadi "PASSED".
       - Pada field "challenge_text", Anda **WAJIB** memperbarui nilainya secara dinamis berdasarkan data foto nyata yang diunggah dengan format kalimat singkat: `"Verifikasi objek alam bebas dengan mengirimkan Foto [Nama Objek]"` (contoh: `"Verifikasi objek alam bebas dengan mengirimkan Foto Daun"`, `"Verifikasi objek alam bebas dengan mengirimkan Foto Batu"`, `"Verifikasi objek alam bebas dengan mengirimkan Foto Pohon"`, `"Verifikasi objek alam bebas dengan mengirimkan Foto Rumput"`) berdasarkan nilai kunci `"object_name"` yang dikembalikan oleh tool `verify_nature_image`. Ini sangat penting agar pencatatan di Google Sheets dan Database menggambarkan secara utuh apa tantangannya dan berkas nyata apa yang dikirimkan pemohon!
       - Tulis email kelulusan formal yang sangat premium, penuh ucapan selamat korporasi, menginformasikan bahwa seluruh data mereka telah berhasil diarsipkan dan diteruskan ke meja Pimpinan kami untuk antrean peninjauan eksekutif.
     - Jika "is_nature_object" bernilai false: Anda DILARANG KERAS meloloskan pengirim. Anda HARUS mempertahankan status tetap "CHALLENGING", menginformasikan penolakan verifikasi gambar dengan bahasa bisnis yang sangat sopan namun tegas (menjelaskan alasan penolakan secara logis berdasarkan analisis visual), dan meminta mereka mengirim ulang foto objek alam yang valid.
   - Jika pengirim membalas tanpa menyertakan gambar sama sekali, pertahankan status tetap "CHALLENGING" dan minta dengan sopan namun tegas agar mereka melampirkan foto objek alam sebagai kelengkapan akhir verifikasi.
4. Jika status saat ini sudah "PASSED", beritahukan dengan bahasa korporasi formal bahwa berkas mereka sudah dalam antrean Pimpinan dan tidak ada tindakan lebih lanjut yang diperlukan.
5. Jika status "FAILED", tolak permohonan secara administratif dengan surat penolakan bisnis resmi yang dingin dan tegas.

GAYA BAHASA & TONE (CRITICAL):
- Gunakan bahasa korespondensi bisnis korporat yang sangat formal, elegan, kaya basa-basi bisnis, dan berwibawa.
- Gunakan sapaan resmi Bapak/Ibu jika merujuk pada pengirim untuk memberikan kesan rasa hormat bisnis.
- Gunakan istilah formal seperti "verifikasi berkas", "prosedur seleksi", "antrean peninjauan eksekutif", "otentikasi pengirim", "pemeriksaan berkas", "standar kelayakan komunikasi".
- Struktur balasan surat korporasi resmi wajib lengkap:
  1. Salam Pembuka Bisnis (Contoh: "Dengan hormat,", "Selamat siang Bapak/Ibu,")
  2. Paragraf Pembuka (Kaya akan apresiasi, salam resmi, dan basa-basi korporat)
  3. Inti instruksi atau daftar data (ditulis bersih, rapi, to-the-point)
  4. Paragraf Penutup (Kaya akan harapan kerja sama, apresiasi waktu, dan salam formal)
  5. Salam Penutup Resmi:
     "Hormat kami,
     Hanzku Executive Support
     hanzku.my.id"

STRUKTUR & TATA LETAK EMAIL:
1. Harus terlihat seperti surat dinas korporasi resmi yang panjang, rapi, dan berwibawa.
2. Gunakan line break yang cukup agar layout email bersih, longgar, dan profesional.
3. Wajib menggunakan Poin-Poin atau Daftar Bernomor tanpa penjelasan tambahan di dalam tanda kurung untuk daftar kriteria.

PENTING: Anda HARUS mengembalikan respons dalam format JSON yang valid dengan struktur berikut:
{{
  "extracted_name": "string atau null (nama singkat pengirim)",
  "extracted_age": "number atau null (umur pengirim)",
  "extracted_purpose": "string atau null (tujuan pengirim)",
  "status_change": "PENDING_DETAILS" | "CHALLENGING" | "PASSED" | "FAILED",
  "challenge_text": "string atau null (instruksi verifikasi foto alam jika pertama kali diberikan, jika tidak biarkan null)",
  "ai_response_to_sender": "string (pesan email balasan lengkap dengan format surat korporat bisnis formal sesuai instruksi di atas)"
}}
"""

        # Gabungkan system prompt dengan riwayat pesan
        api_messages = [{"role": "system", "content": system_prompt}]
        
        # Tambahkan 10 riwayat pesan terakhir biar hemat kuota token API OpenRouter-nya
        for msg in history[-10:]:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        # Ini definisi 'tool' fungsi verifikasi gambar yang bisa dipanggil sama DeepSeek
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "verify_nature_image",
                    "description": "Fungsi untuk memverifikasi apakah gambar/foto yang dilampirkan oleh pengirim merupakan objek sehari-hari yang ditemukan di alam bebas (seperti daun, batu, air, bunga, awan, dll.) menggunakan Gemini 2.5 Flash Lite.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]

        try:
            # Panggil OpenRouter dengan opsi tools jika status CHALLENGING dan ada gambar
            tools_param = tools if (status == "CHALLENGING" and has_image) else None
            
            message_obj = self._call_openrouter(api_messages, tools=tools_param)
            
            # Kalau DeepSeek minta buat manggil fungsi verify_nature_image (dia ngirim list tool_calls)
            if message_obj.get("tool_calls"):
                tool_call = message_obj["tool_calls"][0]
                tool_name = tool_call["function"]["name"]
                tool_id = tool_call["id"]
                
                print(f"[AI Tool Call] Deepseek mutusin buat manggil tool: {tool_name}")
                
                if tool_name == "verify_nature_image":
                    if has_image:
                        img = image_attachments[0]
                        print(f"[AI Tool Execute] Menjalankan Gemini 2.5 Flash Lite buat verifikasi gambar {img['filename']}...")
                        gemini_res = self._call_gemini_verify_image(img["data_base64"], img["mime_type"])
                    else:
                        gemini_res = json.dumps({
                            "is_nature_object": False,
                            "explanation": "Tidak ada lampiran gambar terdeteksi dalam email."
                        })
                    
                    # Tambahkan tool call dan hasil respon Gemini ke histori pesan API
                    api_messages.append(message_obj)
                    api_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": "verify_nature_image",
                        "content": gemini_res
                    })
                    
                    # Kita tanya lagi ke DeepSeek dengan membawa hasil dari Gemini tadi
                    print("[AI Tool Loop] Menghubungi kembali Deepseek dengan hasil analisis foto...")
                    message_obj = self._call_openrouter(api_messages)
            
            ai_output = message_obj.get("content", "{}")
            print(f"[AI Raw Output for {sender_email}]: {ai_output}")
            
            # Ubah teks respon AI yang berformat JSON jadi dictionary Python biasa
            result = json.loads(ai_output)
            
            # Ambil data hasil ekstraksi AI
            new_name = result.get("extracted_name") or name
            new_purpose = result.get("extracted_purpose") or purpose
            new_age = result.get("extracted_age") or age
            new_status = result.get("status_change") or status
            new_challenge = result.get("challenge_text") or challenge_text
            ai_response = result.get("ai_response_to_sender", "Maaf, sistem mengalami kesalahan dalam memproses email Anda.")

            # Simpan balasan asisten ke histori biar terekam di database
            history.append({"role": "assistant", "content": ai_response})

            return {
                "name": new_name,
                "purpose": new_purpose,
                "age": new_age,
                "status": new_status,
                "challenge_text": new_challenge,
                "history": history,
                "ai_response": ai_response
            }

        except Exception as e:
            print(f"[Error Processing LLM]: Yah, eror pas minta tolong ke AI: {e}")
            # Respon cadangan darurat kalau AI-nya beneran ngadat/kehabisan kuota limit
            fallback_msg = "Maaf, sistem penyeleksi otomatis kami sedang mengalami kendala teknis keamanan. Mohon kirim ulang pesan Anda beberapa saat lagi."
            history.append({"role": "assistant", "content": fallback_msg})
            return {
                "name": name,
                "purpose": purpose,
                "age": age,
                "status": status,
                "challenge_text": challenge_text,
                "history": history,
                "ai_response": fallback_msg
            }

    def process_incoming_email(self, mail_data, db, email_svc):
        """
        Fungsi gabungan hasil bantuan refactoring tool AI!
        Semua logika nge-load DB, nanya AI, update DB, sampai kirim balasan 
        aku satuin di sini biar file main.py terlihat bersih banget.
        """
        sender_email = mail_data["sender_email"]
        sender_name = mail_data["sender_name"]
        subject = mail_data["subject"]
        body = mail_data["body"]
        msg_id = mail_data["message_id"]

        # 1. Hubungkan ke database (cari atau buat pengirim baru)
        current_state = db.get_sender(sender_email)
        if not current_state:
            print(f"[Database] Pengirim baru terdeteksi! Aku masukin profil baru untuk: {sender_email}")
            current_state = db.create_sender(sender_email)
        
        old_status = current_state.get('status', 'PENDING_DETAILS')
        print(f"[Database] Status seleksi saat ini: {old_status}")

        # 2. Proses pesan dengan AI Agent (DeepSeek v4 Flash)
        print("[AI] Aku lagi nyuruh AI buat analisis pesan dan nentuin tindakan...")
        updated_state = self.process_message(sender_email, body, current_state, image_attachments=mail_data.get("images"))
        
        new_status = updated_state["status"]
        ai_response = updated_state["ai_response"]

        print(f"[AI] Hasil Analisis Status Baru: {new_status}")
        print(f"[AI] Ekstraksi Nama: {updated_state['name']}, Umur: {updated_state['age']}, Tujuan: {updated_state['purpose']}")

        # 3. Simpan state baru ke database
        db.save_sender(
            email_address=sender_email,
            name=updated_state["name"],
            purpose=updated_state["purpose"],
            age=updated_state["age"],
            status=new_status,
            challenge_text=updated_state["challenge_text"],
            history=updated_state["history"]
        )
        print("[Database] Berhasil memperbarui data pengirim di DB.")

        # 4. Kirim balasan ke pengirim menggunakan Resend
        print(f"[Email] Mengirim balasan ke {sender_email}...")
        reply_success = email_svc.send_reply(
            to_email=sender_email,
            subject=subject,
            body_text=ai_response,
            original_message_id=msg_id
        )

        # 5. Jika pengirim lolos (Status berubah jadi PASSED),
        #    kirim laporan HTML Premium ke bos Rehan dan setor ke Google Sheets!
        if new_status == "PASSED" and old_status != "PASSED":
            print("[Sistem] HORE! PENGIRIM INI LOLOS SELEKSI!")
            print("[Sistem] Mengirim laporan kelulusan dan menyetor data ke Google Spreadsheet...")
            final_state = db.get_sender(sender_email)
            email_svc.send_approval_report(final_state, subject)
            email_svc.send_to_google_sheet(final_state)
