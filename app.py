import base64
import io
import os
import time
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Simulasi TKA SMA/SMK Sederajat (Bank Soal Sheets)",
    page_icon="🎓",
    layout="wide"
)

# 1. INISIALISASI SESSION STATE
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
if "school_name" not in st.session_state:
    st.session_state.school_name = ""
if "school_email" not in st.session_state:
    st.session_state.school_email = ""
if "target_spreadsheet_id" not in st.session_state:
    st.session_state.target_spreadsheet_id = ""
if "role" not in st.session_state:
    st.session_state.role = None
if "sistem_tahap" not in st.session_state:
    st.session_state.sistem_tahap = "login"
if "current_soal_list" not in st.session_state:
    st.session_state.current_soal_list = []
if "df_siswa" not in st.session_state:
    st.session_state.df_siswa = pd.DataFrame(columns=["Sekolah", "Kelas", "No_Absen", "Nama_Siswa"])

# 2. FUNGSI MEMBACA DATABASE MASTER DARI GOOGLE SHEETS
@st.cache_data(ttl=60)
def load_master_registry():
    master_id = "1KCZRIC2boCPYN9iKKOrnBFz_rOxTavWI_mvKFcwzquQ"
    csv_url = f"https://docs.google.com/spreadsheets/d/{master_id}/gviz/tq?tqx=out:csv&sheet=DATABASE_MASTER_REGISTRY_TKA"
    try:
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        return None

# 3. FUNGSI MEMBACA REKAP DATA DARI GOOGLE SHEET SEKOLAH
@st.cache_data(ttl=30)
def load_school_data(spreadsheet_id):
    if not spreadsheet_id:
        return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.sheet1
        rows = worksheet.get_all_values()
        if len(rows) > 1:
            return pd.DataFrame(rows[1:], columns=rows[0])
        elif len(rows) == 1:
            return pd.DataFrame(columns=rows[0])
        return None
    except Exception as e:
        try:
            csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv"
            return pd.read_csv(csv_url)
        except Exception:
            return None

# 4. FUNGSI LOAD & SAVE DATA SISWA KE GOOGLE SHEETS (TAB: Data_Siswa)
def load_student_data_from_sheets(spreadsheet_id):
    if not spreadsheet_id:
        return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(spreadsheet_id)
        
        try:
            ws = sh.worksheet("Data_Siswa")
        except gspread.exceptions.WorksheetNotFound:
            return None
            
        rows = ws.get_all_values()
        if len(rows) > 1:
            return pd.DataFrame(rows[1:], columns=rows[0])
        return None
    except Exception:
        return None

def save_student_data_to_sheets(spreadsheet_id, df):
    if not spreadsheet_id or df.empty:
        return False, "Spreadsheet ID kosong atau data siswa kosong."
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(spreadsheet_id)
        
        try:
            ws = sh.worksheet("Data_Siswa")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="Data_Siswa", rows=1000, cols=10)
            
        ws.clear()
        data_to_write = [df.columns.tolist()] + df.astype(str).values.tolist()
        ws.update(data_to_write)
        return True, "Berhasil"
    except Exception as e:
        return False, str(e)

# 5. FUNGSI MEMBACA BANK SOAL DARI GOOGLE SHEETS (TAB: bank_soal)
@st.cache_data(ttl=60)
def load_bank_soal_from_sheets_tabular(mapel_pilihan, level_paket):
    spreadsheet_id = st.session_state.get("target_spreadsheet_id", "1KCZRIC2boCPYN9iKKOrnBFz_rOxTavWI_mvKFcwzquQ")
    if not spreadsheet_id:
        spreadsheet_id = "1KCZRIC2boCPYN9iKKOrnBFz_rOxTavWI_mvKFcwzquQ"
        
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        
        try:
            sh = gc.open_by_key(spreadsheet_id)
            ws = sh.worksheet("bank_soal")
        except Exception:
            master_id = "1KCZRIC2boCPYN9iKKOrnBFz_rOxTavWI_mvKFcwzquQ"
            sh_master = gc.open_by_key(master_id)
            ws = sh_master.worksheet("bank_soal")
            
        rows = ws.get_all_values()
        if len(rows) > 1:
            df = pd.DataFrame(rows[1:], columns=rows[0])
        else:
            return []
            
        df.columns = df.columns.str.strip()
        
        if "Bahasa Indonesia" in mapel_pilihan:
            target_mapel = "Bahasa Indonesia"
        elif "Bahasa Inggris" in mapel_pilihan:
            target_mapel = "Bahasa Inggris"
        else:
            target_mapel = "Matematika"
            
        if "paket 1" in level_paket.lower():
            keyword_paket = "paket 1"
        else:
            keyword_paket = "paket 2"
            
        df['Mata_Pelajaran_clean'] = df['Mata_Pelajaran'].astype(str).str.strip().str.lower()
        df['Paket_clean'] = df['Paket'].astype(str).str.strip().str.lower()
        
        filtered = df[
            (df['Mata_Pelajaran_clean'].str.contains(target_mapel.lower(), na=False)) & 
            (df['Paket_clean'].str.contains(keyword_paket, na=False))
        ]
        
        soal_list = []
        for idx, row in filtered.iterrows():
            kunci_huruf = str(row['Kunci_Jawaban']).strip().upper()
            mapping_kunci = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
            kunci_idx = mapping_kunci.get(kunci_huruf, 0)
            
            domain = row.get('Domain_Materi', '')
            level_kog = row.get('Level_Kognitif', '')
            kategori_teks = f"{domain} - {level_kog}" if domain or level_kog else "Asesmen TKA"
            
            item_soal = {
                "id": len(soal_list) + 1,
                "kategori": kategori_teks,
                "stimulus": str(row['Pertanyaan']),
                "soal": str(row['Pertanyaan']),
                "opsi": [
                    str(row['Opsi_A']),
                    str(row['Opsi_B']),
                    str(row['Opsi_C']),
                    str(row['Opsi_D']),
                    str(row['Opsi_E'])
                ],
                "kunci": kunci_idx,
                "pembahasan": str(row['Pembahasan'])
            }
            soal_list.append(item_soal)
            
        return soal_list
    except Exception as e:
        st.error(f"Gagal memuat bank soal dari Google Sheets: {e}")
        return []

# --- CSS CUSTOM FLEKSIBEL & TOMBOL BIRU MUDA YANG KONTRAS ---
st.markdown(
    """
    <style>
    /* Mode Gelap otomatis jika laptop menggunakan Dark Mode */
    @media (prefers-color-scheme: dark) {
        .stApp {
            background-color: #0e1117 !important;
            color: #ffffff !important;
        }
        section[data-testid="stSidebar"] {
            background-color: #161b22 !important;
            color: #ffffff !important;
        }
        p, span, label, div, .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
        }
        div[data-testid="stInfo"], div[data-testid="stSuccess"], div[data-testid="stError"], div[data-testid="stWarning"] {
            color: #ffffff !important;
        }
        div[data-testid="stInfo"] p, div[data-testid="stSuccess"] p, div[data-testid="stError"] p, div[data-testid="stWarning"] p {
            color: #ffffff !important;
        }
        div[data-baseweb="radio"] div[role="radio"] {
            border: 2px solid #ffffff !important;
            background-color: #0e1117 !important;
        }
        div[data-baseweb="radio"] div[role="radio"] > div {
            background-color: #ffffff !important;
        }
    }

    /* Mode Terang otomatis jika laptop menggunakan Light Mode */
    @media (prefers-color-scheme: light) {
        .stApp {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        section[data-testid="stSidebar"] {
            background-color: #f1f5f9 !important;
            color: #000000 !important;
        }
        p, span, label, div, .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 {
            color: #000000 !important;
        }
        div[data-testid="stInfo"], div[data-testid="stSuccess"], div[data-testid="stError"], div[data-testid="stWarning"] {
            color: #000000 !important;
        }
        div[data-testid="stInfo"] p, div[data-testid="stSuccess"] p, div[data-testid="stError"] p, div[data-testid="stWarning"] p {
            color: #000000 !important;
        }
        div[data-baseweb="radio"] div[role="radio"] {
            border: 2px solid #000000 !important;
            background-color: #ffffff !important;
        }
        div[data-baseweb="radio"] div[role="radio"] > div {
            background-color: #000000 !important;
        }
    }
    
    /* Tombol Utama: Warna Biru Muda dengan Teks Gelap agar Sangat Terlihat Jelas */
    div.stFormSubmitButton > button {
        background-color: #93c5fd !important;
        color: #0f172a !important;
        font-weight: 800 !important;
        border: 2px solid #3b82f6 !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15) !important;
        width: 100% !important;
    }
    div.stFormSubmitButton > button:hover {
        background-color: #60a5fa !important;
        color: #000000 !important;
        border-color: #2563eb !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# 6. TAMPILAN HALAMAN LOGIN SEKOLAH
if not st.session_state.is_logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if os.path.exists("logo.png"):
            with open("logo.png", "rb") as image_file:
                encoded_logo = base64.b64encode(image_file.read()).decode()
            st.markdown(
                f"""
                <div style="text-align: center; margin-bottom: 10px;">
                    <img src="data:image/png;base64,{encoded_logo}" width="70" style="display: inline-block;">
                </div>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown("<h2 style='text-align: center;'>Simulasi TKA Cabdin Bangkalan</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; font-weight: 700;'>Silakan masukkan Email dan Token Unik sekolah Anda yang terdaftar.</p>", unsafe_allow_html=True)
        
        with st.form("form_login_sekolah"):
            input_email = st.text_input("Email Resmi Sekolah", placeholder="contoh: smansabkl@yahoo.co.id")
            input_token = st.text_input("Token Unik / Password", type="password", placeholder="contoh: TKA-123")
            
            submit_login = st.form_submit_button("Masuk ke Sistem Ujian", use_container_width=True)
            
            if submit_login:
                df_master = load_master_registry()
                if df_master is not None and not df_master.empty:
                    clean_email = input_email.strip().lower()
                    clean_token = input_token.strip()
                    
                    df_master.columns = df_master.columns.str.strip()
                    matched = df_master[df_master['Email'].astype(str).str.strip().str.lower() == clean_email]
                    
                    if not matched.empty:
                        row = matched.iloc[0]
                        db_token = str(row['Token_Unik']).strip()
                        db_status = str(row['Status']).strip().upper()
                        
                        if db_status == "AKTIF":
                            if clean_token == db_token:
                                st.session_state.is_logged_in = True
                                st.session_state.school_name = row['Nama_Sekolah']
                                st.session_state.school_email = row['Email']
                                
                                sheet_id = row['Spreadsheet_ID']
                                if pd.notna(sheet_id) and str(sheet_id).strip() != "":
                                    st.session_state.target_spreadsheet_id = str(sheet_id).strip()
                                    
                                    df_cloud = load_student_data_from_sheets(st.session_state.target_spreadsheet_id)
                                    if df_cloud is not None and not df_cloud.empty:
                                        st.session_state.df_siswa = df_cloud
                                else:
                                    st.session_state.target_spreadsheet_id = ""
                                    
                                if "pusat" in clean_email or "yusbuset" in clean_email:
                                    st.session_state.role = "admin"
                                else:
                                    st.session_state.role = "sekolah"
                                    
                                st.success(f"Login Berhasil! Selamat datang, {row['Nama_Sekolah']}")
                                st.rerun()
                            else:
                                st.error("Token Unik / Password salah!")
                        else:
                            st.error("Akun sekolah ini berstatus TIDAK AKTIF.")
                    else:
                        st.error("Email sekolah tidak terdaftar di Database Master Registry!")
                else:
                    st.error("Gagal membaca data dari Google Sheets Master Registry.")

        st.markdown(
            """
            <div style='text-align: center; font-size: 0.9em; font-weight: 700; margin-top: 25px;'>
                Pengembang: <b>Yustinus Budi Setyanta - PS Cabdin Bangkalan</b>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.stop()

def evaluasi_hasil(mapel, nilai):
    if nilai >= 85.00:
        kategori = "Sangat Mahir"
    elif nilai >= 75.00:
        kategori = "Mahir"
    elif nilai >= 60.00:
        kategori = "Cakap"
    else:
        kategori = "Perlu Intervensi Khusus"

    if "Matematika" in mapel:
        deskripsi = "Penguasaan konsep numerasi, aljabar, dan pemecahan masalah tingkat lanjut."
    elif "Bahasa Inggris" in mapel:
        deskripsi = "Kemampuan membaca, menganalisis teks fungsional/analitis, dan tata bahasa."
    else:
        deskripsi = "Kemampuan literasi membaca teks informasi dan sastra secara kritis."

    return kategori, deskripsi

def simpan_hasil_ke_google_sheets(tanggal, nama, kelas, sekolah, mapel, nilai, kategori, deskripsi):
    spreadsheet_id = st.session_state.get("target_spreadsheet_id", "")
    if not spreadsheet_id:
        return

    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)

        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.sheet1

        val_indo = nilai if "Bahasa Indonesia" in mapel else ""
        val_inggris = nilai if "Bahasa Inggris" in mapel else ""
        val_matematika = nilai if "Matematika" in mapel else ""

        row_data = [sekolah, kelas, str(tanggal), nama, val_indo, val_inggris, val_matematika]
        worksheet.append_row(row_data)
    except Exception as e:
        st.warning(f"Catatan: Gagal sinkron ke Google Sheet sekolah: {e}")

# --- SIDEBAR NAVIGASI MENU ---
st.sidebar.markdown(f"### 🏫 {st.session_state.school_name}")
st.sidebar.markdown(f"**Email:** {st.session_state.school_email}")
st.sidebar.markdown("---")

menu_pilihan = st.sidebar.radio(
    "Pilih Halaman:",
    ["Simulasi Ujian", "Manajemen Data Siswa", "Rekap Hasil TKA", "Download Hasil TKA"],
)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout / Keluar", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.markdown(
    """
    <div style='text-align: center; font-size: 0.85em; font-weight: 700; padding-top: 10px;'>
        Pengembang Aplikasi:<br>
        <b>Yusbuset@2026</b>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# MENU 1: SIMULASI UJIAN
# ==========================================
if menu_pilihan == "Simulasi Ujian":
    if st.session_state.sistem_tahap == "login":
        st.markdown(
            """
            <div style='text-align: center; line-height: 1.2; margin-bottom: 10px;'>
                <h2 style='margin: 0px; padding: 0px;'>Uji Coba TKA SMA/SMK - Cabdin Bangkalan</h2>
                <h3 style='margin: 2px 0px 0px 0px; padding: 0px;'>Berbasis Bank Soal Terpadu</h3>
            </div>
            <p style='text-align: center; font-weight: 700; margin: 0px 0px 10px 0px;'>
                Silakan pilih Kelas dan Nama Siswa dari data yang telah diunggah melalui menu Manajemen Data Siswa.
            </p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")

        tanggal_simulasi = st.date_input("Tanggal Simulasi", value=pd.Timestamp.today())
        sekolah_siswa = st.text_input("Asal Sekolah", value=st.session_state.get("school_name", ""))
        
        df_siswa = st.session_state.get("df_siswa", pd.DataFrame())
        
        if not df_siswa.empty:
            target_sekolah = sekolah_siswa.strip().lower() if sekolah_siswa else st.session_state.school_name.strip().lower()
            df_sekolah_filter = df_siswa[df_siswa["Sekolah"].astype(str).str.strip().str.lower() == target_sekolah]
            if df_sekolah_filter.empty:
                df_sekolah_filter = df_siswa
            
            daftar_kelas = df_sekolah_filter["Kelas"].dropna().unique().tolist()
        else:
            daftar_kelas = []

        if len(daftar_kelas) > 0:
            pilih_kelas = st.selectbox("Pilih Kelas", daftar_kelas)
            daftar_nama = df_sekolah_filter[df_sekolah_filter["Kelas"] == pilih_kelas]["Nama_Siswa"].dropna().unique().tolist()
            pilih_nama_siswa = st.selectbox("Pilih Nama Siswa", daftar_nama)
            
            kelas_siswa = pilih_kelas
            nama_siswa = pilih_nama_siswa
        else:
            st.warning("⚠️ Belum ada data siswa. Silakan download template dan upload/sinkronkan data siswa melalui menu **Manajemen Data Siswa**.")
            kelas_siswa = st.text_input("Kelas", value="Kelas XII")
            nama_siswa = st.text_input("Nama Lengkap Siswa (Manual)")
        
        pilih_mapel = st.selectbox(
            "Pilih Mata Pelajaran TKA", 
            ["Bahasa Indonesia", "Bahasa Inggris", "Matematika"]
        )
        
        pilih_paket = st.radio(
            "Pilih Level Paket Soal",
            ["Paket 1 (Standar)", "Paket 2 (Tingkat Lanjut - Lebih Sulit)"],
            horizontal=True
        )

        st.markdown("")
        if st.button("Mulai Simulasi Ujian", use_container_width=True):
            if nama_siswa and sekolah_siswa:
                st.session_state.tanggal = tanggal_simulasi
                st.session_state.nama = nama_siswa
                st.session_state.kelas = kelas_siswa
                st.session_state.sekolah = sekolah_siswa
                st.session_state.mapel_aktif = f"{pilih_mapel} - {pilih_paket}"
                
                durasi_menit = 90
                
                with st.spinner(f"📥 Mengambil soal {pilih_mapel} ({pilih_paket}) dari Google Spreadsheet (bank_soal)..."):
                    st.session_state.current_soal_list = load_bank_soal_from_sheets_tabular(pilih_mapel, pilih_paket)
                
                if not st.session_state.current_soal_list:
                    st.error("⚠️ Tidak ada soal yang ditemukan di Spreadsheet untuk kombinasi Mata Pelajaran dan Paket tersebut.")
                else:
                    st.session_state.end_time = time.time() + (durasi_menit * 60)
                    st.session_state.sistem_tahap = "ujian"
                    st.session_state.jawaban_peserta = {}
                    st.rerun()
            else:
                st.warning("Mohon lengkapi Nama Siswa dan Asal Sekolah terlebih dahulu!")

    elif st.session_state.sistem_tahap == "ujian":
        mapel = st.session_state.mapel_aktif
        soal_list = st.session_state.current_soal_list

        sisa_detik = int(st.session_state.end_time - time.time())
        if sisa_detik <= 0:
            st.warning("Waktu ujian telah habis!")
            st.session_state.sistem_tahap = "hasil"
            st.rerun()

        st.markdown(f"### 📝 Ujian: {mapel}")
        st.markdown(
            f"**Peserta:** {st.session_state.nama} ({st.session_state.kelas})"
            f" | **Asal:** {st.session_state.sekolah} | **Total Soal:** {len(soal_list)} Butir"
        )

        timer_html = f"""
        <div style="background-color: #5c1d1d; border: 1px solid #8b2626; padding: 12px; border-radius: 8px; color: #ffcccc; text-align: center; font-family: sans-serif;">
            ⏳ <b>Sisa Waktu Ujian:</b> <span id="countdown" style="font-weight: bold; font-size: 1.2em;">Menghitung...</span>
        </div>
        <script>
            var endTime = {st.session_state.end_time * 1000};
            function updateTimer() {{
                var now = new Date().getTime();
                var distance = endTime - now;
                if (distance < 0) {{
                    document.getElementById("countdown").innerHTML = "Waktu Habis!";
                    window.location.reload();
                    return;
                }}
                var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                var seconds = Math.floor((distance % (1000 * 60)) / 1000);
                
                var timeString = "";
                if (hours > 0) {{ timeString += hours + " Jam "; }}
                timeString += minutes + " Menit " + seconds + " Detik";
                document.getElementById("countdown").innerHTML = timeString;
            }}
            setInterval(updateTimer, 1000);
            updateTimer();
        </script>
        """
        components.html(timer_html, height=60)
        st.markdown("---")

        jawaban_sementara = {}

        with st.form("form_soal_sheets"):
            for idx, item in enumerate(soal_list):
                st.markdown(f"**Soal {idx+1} dari {len(soal_list)}** &nbsp;&nbsp;|&nbsp;&nbsp; *{item.get('kategori', 'Asesmen TKA')}*")
                st.info(f"{item.get('stimulus', '')}")
                
                pilihan = st.radio(
                    f"Pilih jawaban soal {idx+1}:",
                    item.get("opsi", []),
                    key=f"soal_sh_{idx}",
                    index=None,
                )
                jawaban_sementara[idx] = pilihan
                st.markdown("---")

            submitted_ujian = st.form_submit_button("Selesai & Kumpulkan Jawaban", use_container_width=True)

            if submitted_ujian:
                st.session_state.jawaban_peserta = jawaban_sementara
                st.session_state.sistem_tahap = "hasil"
                st.rerun()

    elif st.session_state.sistem_tahap == "hasil":
        mapel = st.session_state.mapel_aktif
        soal_list = st.session_state.current_soal_list

        skor = 0
        total_soal = len(soal_list)

        st.markdown("<h3 style='text-align: center;'>📊 Hasil Simulasi TKA (Bank Soal Spreadsheet)</h3>", unsafe_allow_html=True)
        st.info(
            f"**Tanggal:** {st.session_state.tanggal} | **Nama:**"
            f" {st.session_state.nama} | **Kelas:** {st.session_state.kelas} |"
            f" **Mata Ujian:** {mapel}"
        )

        for idx, item in enumerate(soal_list):
            jawaban_user = st.session_state.jawaban_peserta.get(idx)
            kunci_idx = item.get("kunci", 0)
            opsi_list = item.get("opsi", [])
            kunci_jawaban_tepat = opsi_list[kunci_idx] if len(opsi_list) > kunci_idx else ""

            st.markdown(f"**Soal {idx+1}** *({item.get('kategori', '')})*")
            st.info(f"{item.get('stimulus', '')}")

            if jawaban_user == kunci_jawaban_tepat:
                skor += 1
                st.success(f"**Status: Benar!** (Jawaban Anda: {jawaban_user})")
            else:
                st.error(f"**Status: Salah.** (Jawaban Anda: {jawaban_user or 'Tidak dijawab'}, Kunci: {kunci_jawaban_tepat})")

            st.markdown(f"💡 *Pembahasan:* {item.get('pembahasan', '')}")
            st.markdown("---")

        nilai_akhir = round((skor / total_soal) * 100, 2) if total_soal > 0 else 0
        kategori, deskripsi = evaluasi_hasil(mapel, nilai_akhir)

        st.metric(label="Nilai Akhir Simulasi TKA", value=f"{nilai_akhir:.2f} / 100")
        st.info(f"🏆 **Kategori Pencapaian:** **{kategori}**")
        st.success(f"📖 **Deskripsi Kemampuan:** {deskripsi}")
        st.markdown("---")

        simpan_hasil_ke_google_sheets(
            st.session_state.tanggal,
            st.session_state.nama,
            st.session_state.kelas,
            st.session_state.sekolah,
            mapel,
            f"{nilai_akhir:.2f}",
            kategori,
            deskripsi,
        )
        st.success("✅ Hasil ujian berhasil dicatat ke Google Sheet sekolah Anda!")

        if st.button("🔄 Ulangi Simulasi", use_container_width=True):
            temp_df_siswa = st.session_state.get("df_siswa", pd.DataFrame())
            temp_school = st.session_state.get("school_name", "")
            temp_sheet_id = st.session_state.get("target_spreadsheet_id", "")
            
            st.session_state.clear()
            
            if not temp_df_siswa.empty:
                st.session_state.df_siswa = temp_df_siswa
            if temp_school:
                st.session_state.school_name = temp_school
            if temp_sheet_id:
                st.session_state.target_spreadsheet_id = temp_sheet_id
                
            st.session_state.is_logged_in = True
            st.session_state.sistem_tahap = "login"
            st.rerun()
            
        if st.button("🚪 Keluar / Selesai", use_container_width=True):
            temp_df_siswa = st.session_state.get("df_siswa", pd.DataFrame())
            temp_school = st.session_state.get("school_name", "")
            temp_sheet_id = st.session_state.get("target_spreadsheet_id", "")
            
            st.session_state.clear()
            
            if not temp_df_siswa.empty:
                st.session_state.df_siswa = temp_df_siswa
            if temp_school:
                st.session_state.school_name = temp_school
            if temp_sheet_id:
                st.session_state.target_spreadsheet_id = temp_sheet_id
                
            st.session_state.is_logged_in = True
            st.session_state.sistem_tahap = "login"
            st.rerun()

# ==========================================
# MENU 2: MANAJEMEN DATA SISWA
# ==========================================
elif menu_pilihan == "Manajemen Data Siswa":
    st.markdown("## 📋 Manajemen Data Sekolah & Siswa")
    st.markdown("Unduh template format data siswa dari Google Drive, isi sesuai kelas dan nama siswa, lalu unggah dan sinkronkan ke Spreadsheet sekolah masing-masing agar data tersimpan permanen.")
    st.markdown("---")

    st.subheader("1. Download Template Data Siswa")
    st.link_button(
        "📥 Download Template Data Siswa (Google Drive)",
        "https://docs.google.com/spreadsheets/d/1s0OUWggEJ5SGvElDqZIkh34JLepllifS/edit?usp=sharing&ouid=113462802502772439662&rtpof=true&sd=true",
        use_container_width=True
    )

    st.markdown("---")

    st.subheader("2. Upload & Sinkronisasi Data Siswa ke Spreadsheet Sekolah")
    uploaded_file = st.file_uploader("Pilih file CSV atau Excel data siswa", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_uploaded = pd.read_csv(uploaded_file)
            else:
                df_uploaded = pd.read_excel(uploaded_file)
            
            expected_cols = ["Sekolah", "Kelas", "No_Absen", "Nama_Siswa"]
            
            if all(col in df_uploaded.columns for col in expected_cols):
                st.session_state.df_siswa = df_uploaded
                st.success(f"✅ Berhasil memuat {len(df_uploaded)} data siswa ke memori aplikasi!")
            else:
                st.error(f"❌ Format kolom salah! Kolom wajib: {expected_cols}")
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")

    if not st.session_state.df_siswa.empty:
        st.markdown("")
        if st.button("☁️ Unggah & Sinkronkan Data ke Spreadsheet Sekolah", use_container_width=True):
            sheet_id = st.session_state.get("target_spreadsheet_id", "")
            if not sheet_id:
                st.error("Spreadsheet ID sekolah Anda belum terkonfigurasi di Master Registry.")
            else:
                with st.spinner("Sedang mengunggah data siswa ke Google Spreadsheet..."):
                    success, msg = save_student_data_to_sheets(sheet_id, st.session_state.df_siswa)
                    if success:
                        st.success("🎉 Data siswa berhasil diunggah dan disimpan permanen ke Google Spreadsheet sekolah Anda!")
                    else:
                        st.error(f"Gagal mengunggah ke spreadsheet: {msg}")

    st.markdown("---")
    st.markdown("### 👁️ Preview Data Siswa Aktif di Sistem:")
    
    if st.button("🔄 Muat Ulang Data dari Spreadsheet Sekolah"):
        sheet_id = st.session_state.get("target_spreadsheet_id", "")
        if sheet_id:
            df_cloud = load_student_data_from_sheets(sheet_id)
            if df_cloud is not None and not df_cloud.empty:
                st.session_state.df_siswa = df_cloud
                st.success("Data siswa berhasil dimuat ulang dari Google Spreadsheet!")
                st.rerun()
            else:
                st.info("Belum ada data siswa yang tersimpan di Spreadsheet sekolah.")

    df_current = st.session_state.get("df_siswa", pd.DataFrame())
    if not df_current.empty:
        st.dataframe(df_current, use_container_width=True)
    else:
        st.info("Belum ada data siswa yang diunggah.")

# ==========================================
# MENU 3: REKAP HASIL TKA
# ==========================================
elif menu_pilihan == "Rekap Hasil TKA":
    st.markdown("## 📈 Rekap Hasil TKA Mandiri Sekolah")
    st.markdown(f"Menampilkan data rekapitulasi ujian siswa dari Google Sheet sekolah: **{st.session_state.school_name}**")
    st.markdown("---")

    spreadsheet_id = st.session_state.get("target_spreadsheet_id", "")
    if not spreadsheet_id:
        st.warning("⚠️ Spreadsheet ID untuk sekolah ini belum dikonfigurasi di Database Master Registry.")
    else:
        with st.spinner("Memuat data rekapitulasi dari Google Sheets..."):
            df_rekap = load_school_data(spreadsheet_id)

        if df_rekap is not None and not df_rekap.empty:
            st.metric("Total Data Ujian Tercatat", len(df_rekap))
            st.dataframe(df_rekap, use_container_width=True)
        else:
            st.info("Belum ada data hasil ujian yang tercatat di Google Sheet sekolah Anda.")

# ==========================================
# MENU 4: DOWNLOAD HASIL TKA (EXCEL DENGAN KOLOM RAPI)
# ==========================================
elif menu_pilihan == "Download Hasil TKA":
    st.markdown("## 📥 Download Rekap Hasil TKA")
    st.markdown(f"Unduh rekapitulasi nilai ujian untuk **{st.session_state.school_name}** dalam format Excel (.xlsx)")
    st.markdown("---")

    spreadsheet_id = st.session_state.get("target_spreadsheet_id", "")
    if not spreadsheet_id:
        st.warning("⚠️ Spreadsheet ID tidak ditemukan.")
    else:
        df_rekap = load_school_data(spreadsheet_id)
        if df_rekap is not None and not df_rekap.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_rekap.to_excel(writer, index=False, sheet_name='Rekap Hasil TKA')
                worksheet = writer.sheets['Rekap Hasil TKA']
                for col in worksheet.columns:
                    max_length = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = max(max_length + 3, 15)
                    worksheet.column_dimensions[column].width = adjusted_width
            
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Unduh Rekap Data (Excel .xlsx)",
                data=excel_data,
                file_name=f"rekap_tka_{st.session_state.school_name.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("Tidak ada data yang dapat diunduh saat ini.")
