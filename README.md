# siskp-jadwal-notifier

Agent Python untuk memantau halaman publik jadwal ujian SISKP Universitas Negeri Gorontalo dan mengirim notifikasi ke Telegram jika ada jadwal baru atau ada jadwal yang cocok dengan nama/NIM tertentu.

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
- Notifikasi Telegram untuk jadwal umum dan jadwal pribadi.
- Mode `--test-telegram` untuk uji kirim pesan bot tanpa scraping.
- Mode `--seed-existing` untuk menandai semua jadwal saat ini sebagai sudah dilihat tanpa kirim notifikasi.
- Penyimpanan state di `data/sent_schedules.json`.
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
TELEGRAM_BOT_TOKEN=isi_token_bot
TELEGRAM_CHAT_ID=isi_chat_id
MY_NAME=Nama Kamu
MY_NIM=5314xxxx
CHECK_NEXT_MONTH=true
STORAGE_PATH=data/sent_schedules.json
TIMEZONE=Asia/Makassar
```

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

Fungsi ini akan membaca jadwal SISKP yang sudah ada, menyimpannya ke state, tetapi tidak mengirim notifikasi Telegram. Gunakan ini pertama kali sebelum menjalankan bot secara normal agar bot tidak mengirim banyak jadwal lama.

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

- Jalan otomatis tiap 30 menit dengan cron UTC.
- Bisa dijalankan manual lewat `workflow_dispatch`.
- Menggunakan GitHub Secrets untuk token dan chat ID.
- Menjalankan `python main.py` tanpa input manual.
- Commit balik hanya file `data/sent_schedules.json` jika berubah.

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
  - cron: "*/30 * * * *"
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
- Cron `*/30 * * * *` berarti tiap 30 menit.
- Jika branch repository diproteksi dan tidak mengizinkan `github-actions[bot]` push, maka state tidak bisa tersimpan.
- Jika state tidak tersimpan, jadwal lama bisa terkirim ulang.
- Jika struktur HTML berubah, parser tetap mencoba membaca semua tabel dan menyimpan `raw_text` sebagai fallback.
- Jangan simpan token Telegram di kode, workflow, atau README.

## Format Notifikasi

Jadwal umum baru:

```text
[Jadwal Ujian SISKP Baru]

Bulan: 2026-06
Nama: ...
NIM: ...
Jenis Ujian: ...
Tanggal: ...
Jam: ...
Tempat: ...
Judul: ...
Penguji: ...

Link:
https://siskp.informatika.ft.ung.ac.id/masuk/jadwal/2026-06
```

Jadwal pribadi:

```text
[PENTING] Jadwal Ujian Kamu Terdeteksi

Nama: ...
NIM: ...
Jenis Ujian: ...
Tanggal: ...
Jam: ...
Tempat: ...
Judul: ...
Penguji: ...

Segera cek SISKP:
https://siskp.informatika.ft.ung.ac.id/masuk/jadwal/2026-06
```
