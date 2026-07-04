# siskp-jadwal-notifier

Agent Python untuk memantau halaman publik SISKP Universitas Negeri Gorontalo dan mengirim notifikasi ke Telegram jika ada jadwal ujian baru, pendaftar ujian baru, riwayat skripsi baru, atau ada jadwal yang cocok dengan nama/NIM tertentu.

Project ini:

- Tidak perlu login.
- Tidak perlu domain.
- Tidak memakai WhatsApp.
- Bisa dijalankan lokal di laptop.
- Bisa dijalankan otomatis lewat GitHub Actions.

## Fitur

- Otomatis cek bulan berjalan.
- Opsional cek bulan berikutnya dengan `CHECK_NEXT_MONTH=true`.
- Parser tabel yang fleksibel dengan fallback `raw_text`.
- Deteksi jadwal baru berbasis hash unik.
- Deteksi pendaftar ujian baru berbasis hash unik.
- Deteksi riwayat skripsi baru berbasis hash unik.
- Notifikasi Telegram untuk jadwal umum dan jadwal pribadi.
- Ringkasan total jadwal per bulan terpantau pada pesan notifikasi.
- Mode `--test-telegram` untuk uji kirim pesan bot tanpa scraping.
- Mode `--seed-existing` untuk menandai semua jadwal saat ini sebagai sudah dilihat tanpa kirim notifikasi.
- Heartbeat opsional saat tidak ada jadwal baru.
- Penyimpanan state di `data/sent_schedules.json`.
- Penyimpanan state pendaftar ujian di `data/sent_exam_registrations.json`.
- Penyimpanan state riwayat skripsi di `data/sent_thesis_history.json`.
- Penyimpanan heartbeat di `data/heartbeat_state.json`.
- Workflow GitHub Actions yang bisa commit balik file state agar notifikasi tidak berulang.

## Struktur Project

```text
siskp-jadwal-notifier/
|- main.py
|- config.py
|- scraper.py
|- storage.py
|- notifier.py
|- requirements.txt
|- .env.example
|- README.md
`- .github/
   `- workflows/
      `- schedule.yml
```

## Cara Membuat Bot Telegram

1. Buka Telegram lalu chat ke `@BotFather`.
2. Jalankan `/newbot`.
3. Ikuti instruksi sampai dapat token bot.
4. Simpan token itu untuk `TELEGRAM_BOT_TOKEN`.

## Cara Mendapatkan TELEGRAM_CHAT_ID

1. Kirim pesan apa saja ke bot yang baru dibuat.
2. Buka:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

3. Cari nilai `chat.id` pada response JSON.
4. Masukkan nilainya ke `TELEGRAM_CHAT_ID`.

## Menjalankan Secara Lokal

1. Install dependency:

```bash
pip install -r requirements.txt
```

2. Buat file env:

```bash
cp .env.example .env
```

Di Windows PowerShell bisa pakai:

```powershell
Copy-Item .env.example .env
```

3. Isi `.env`:

```env
SISKP_BASE_URL=https://siskp.informatika.ft.ung.ac.id/masuk/jadwal
SISKP_PUBLIC_BASE_URL=https://siskp.informatika.ft.ung.ac.id/masuk
TELEGRAM_BOT_TOKEN=isi_token_bot
TELEGRAM_CHAT_ID=isi_chat_id
MY_NAME=Nama Kamu
MY_NIM=5314xxxx
CHECK_NEXT_MONTH=true
STORAGE_PATH=data/sent_schedules.json
EXAM_REGISTRATION_STORAGE_PATH=data/sent_exam_registrations.json
THESIS_HISTORY_STORAGE_PATH=data/sent_thesis_history.json
PUBLIC_LIST_MAX_PAGES=3
TIMEZONE=Asia/Makassar
SEND_NO_UPDATE_NOTIFICATION=false
NO_UPDATE_NOTIFICATION_EVERY_RUN=false
HEARTBEAT_INTERVAL_MINUTES=180
HEARTBEAT_STATE_PATH=data/heartbeat_state.json
```

`PUBLIC_LIST_MAX_PAGES` membatasi berapa halaman terdepan yang dibaca untuk `Pendaftar Ujian` dan `Riwayat Skripsi`. Default `3`, supaya bot fokus ke data terbaru dan tidak menarik ratusan halaman pada setiap run.

4. Jalankan:

```bash
python main.py
```

## Opsi CLI

Kirim test Telegram tanpa scraping atau menyentuh file state:

```bash
python main.py --test-telegram
```

Tandai semua jadwal yang saat ini ada sebagai sudah dilihat tanpa kirim notifikasi:

```bash
python main.py --seed-existing
```

Seed bulan tertentu saja:

```bash
python main.py --month 2026-06 --seed-existing
```

### Menandai jadwal lama agar tidak dikirim sebagai notif baru

Jalankan:

```bash
python main.py --seed-existing
```

Atau untuk bulan tertentu:

```bash
python main.py --month 2026-06 --seed-existing
```

Fungsi ini akan membaca jadwal ujian, pendaftar ujian, dan riwayat skripsi yang sudah ada, menyimpannya ke state, tetapi tidak mengirim notifikasi Telegram. Gunakan ini pertama kali sebelum menjalankan bot secara normal agar bot tidak mengirim banyak data lama.

## Heartbeat / Notifikasi Jika Tidak Ada Jadwal Baru

Secara default bot hanya mengirim Telegram jika ada jadwal baru.

Jika ingin bot mengirim kabar bahwa belum ada jadwal baru, aktifkan:

```env
SEND_NO_UPDATE_NOTIFICATION=true
```

Konfigurasi rekomendasi:

```env
SEND_NO_UPDATE_NOTIFICATION=true
NO_UPDATE_NOTIFICATION_EVERY_RUN=false
HEARTBEAT_INTERVAL_MINUTES=180
```

Artinya bot cek setiap 5 menit, jadwal baru tetap langsung dikirim, sedangkan pesan "belum ada data baru" dikirim maksimal 1 kali per 3 jam.

Jika benar-benar ingin pesan setiap run atau setiap 5 menit:

```env
SEND_NO_UPDATE_NOTIFICATION=true
NO_UPDATE_NOTIFICATION_EVERY_RUN=true
```

Peringatan: mode setiap 5 menit akan mengirim sekitar 288 pesan per hari jika tidak ada jadwal baru. Itu tidak disarankan kecuali untuk testing singkat.

## Deploy Ke GitHub Actions

1. Buat repository GitHub.
2. Push project ke GitHub.
3. Buka `Settings > Secrets and variables > Actions`.
4. Tambahkan secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `MY_NAME`
   - `MY_NIM`
5. Pastikan `.env` tidak ikut terupload.
6. Jalankan seed lokal terlebih dahulu:

```bash
python main.py --seed-existing
```

7. Commit file state hasil seed:

```bash
git add data/sent_schedules.json
git commit -m "chore: seed existing SISKP schedules"
git push
```

8. Setelah itu GitHub Actions akan berjalan otomatis sesuai jadwal.
9. Jika ingin tes manual, buka tab `Actions > SISKP Jadwal Notifier > Run workflow`.

Workflow ini:

- Jalan otomatis tiap 5 menit dengan cron UTC.
- Bisa dijalankan manual lewat `workflow_dispatch`.
- Menggunakan GitHub Secrets untuk token dan chat ID.
- Menjalankan `python main.py` tanpa input manual.
- Commit balik file state `data/sent_schedules.json`, `data/sent_exam_registrations.json`, `data/sent_thesis_history.json`, dan `data/heartbeat_state.json` jika berubah.

## Fallback Jika GitHub Actions Schedule Tidak Muncul

Jika scheduled run GitHub Actions tidak muncul otomatis, workflow tetap bisa dijalankan dari luar menggunakan API `workflow_dispatch` GitHub.

Endpoint:

```text
POST https://api.github.com/repos/zamaludinhulantu/jadwal_notif/actions/workflows/schedule.yml/dispatches
```

Header:

```text
Accept: application/vnd.github+json
Authorization: Bearer <GITHUB_TOKEN>
X-GitHub-Api-Version: 2022-11-28
```

Body JSON:

```json
{"ref":"main"}
```

### Membuat GitHub Fine-grained Personal Access Token

1. Buka `GitHub -> Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens`.
2. Klik `Generate new token`.
3. Pada `Repository access`, pilih `Only select repositories`.
4. Pilih repo `zamaludinhulantu/jadwal_notif`.
5. Pada `Repository permissions`, aktifkan:
   - `Actions: Read and write`
   - `Contents: Read and write`
6. Klik `Generate token`.
7. Simpan token dengan aman dan jangan commit ke repo.

### Memakai cron-job.org

1. Buat akun di `cron-job.org`.
2. Klik `Create cronjob`.
3. Isi `URL` dengan endpoint dispatches di atas.
4. Pilih method `POST`.
5. Atur schedule `every 5 minutes`.
6. Tambahkan headers sesuai contoh di atas.
7. Isi body:

```json
{"ref":"main"}
```

Catatan:

- Jika cron eksternal aktif, trigger schedule GitHub boleh tetap ada sebagai cadangan.
- Trigger `push` boleh dihapus nanti jika sudah tidak dibutuhkan.
- Jangan menyimpan GitHub token di kode.

## Menjalankan Manual Untuk Bulan Tertentu

Untuk cek bulan tertentu:

```bash
python main.py --month 2026-06
```

Untuk cek beberapa bulan sekaligus:

```bash
python main.py --month 2026-06 --month 2026-07
```

## Mengubah Interval Pengecekan

Edit file `.github/workflows/schedule.yml`, lalu ubah nilai cron. Contoh saat ini:

```yaml
schedule:
  - cron: "*/5 * * * *"
```

Kalau ingin setiap 1 jam, ubah menjadi:

```yaml
schedule:
  - cron: "0 * * * *"
```

## Catatan Penting

- Script ini hanya membaca halaman publik SISKP.
- Script ini tidak melakukan login.
- Domain tambahan tidak diperlukan.
- GitHub Actions menggunakan waktu UTC untuk cron.
- Cron `*/5 * * * *` berarti jalan tiap 5 menit, termasuk tepat di menit `00` setiap jam.
- Jika branch repository diproteksi dan tidak mengizinkan `github-actions[bot]` push, maka state tidak bisa tersimpan.
- Jika state tidak tersimpan, jadwal lama, pendaftar ujian lama, riwayat skripsi lama, atau heartbeat bisa terkirim ulang.
- Jika struktur HTML berubah, parser tetap mencoba membaca semua tabel dan menyimpan `raw_text` sebagai fallback.
- Jangan simpan token Telegram di kode, workflow, atau README.

## Format Notifikasi

Jadwal umum baru:

```text
✅✅✅✅✅ Jadwal Ujian SISKP Baru

Bulan: 2026-06
Nama: ...
NIM: ...
Jenis Ujian: ...
Tanggal: ...
Jam: ...
Tempat: ...
Judul: ...
Penguji: ...

Total jadwal bulan terpantau:
- 2026-06: 24
- 2026-07: 3

Link:
https://siskp.informatika.ft.ung.ac.id/masuk/jadwal/2026-06
```

Jadwal pribadi:

```text
✅✅✅✅✅ PENTING: Jadwal Ujian Kamu Terdeteksi

Nama: ...
NIM: ...
Jenis Ujian: ...
Tanggal: ...
Jam: ...
Tempat: ...
Judul: ...
Penguji: ...

Total jadwal bulan terpantau:
- 2026-06: 24
- 2026-07: 3

Segera cek SISKP:
https://siskp.informatika.ft.ung.ac.id/masuk/jadwal/2026-06
```

Heartbeat:

```text
ℹ️ Bot SISKP aktif

❌❌❌ Belum ada jadwal ujian, pendaftar ujian, atau riwayat skripsi baru.
Total jadwal bulan terpantau:
- 2026-06: 24
- 2026-07: 3

Cek terakhir: 25 Juni 2026 10:45 WITA
Sumber: SISKP Jadwal Ujian
```

Pendaftar ujian baru:

```text
✅✅✅✅✅ 📝 Pendaftar Ujian Baru

Nama: ...
NIM: ...
Jenis Ujian: ...
Judul: ...
Status: ...
Waktu Daftar: ...

Detail:
https://siskp.informatika.ft.ung.ac.id/masuk/ujian/1234
```

Riwayat skripsi baru:

```text
✅✅✅✅✅ 📚 Riwayat Skripsi Baru

Nama: ...
NIM: ...
Judul: ...
Tahapan: ...

Detail:
https://siskp.informatika.ft.ung.ac.id/masuk/riwayat-skripsi/1234
```
