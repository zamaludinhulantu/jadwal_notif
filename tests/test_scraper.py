import unittest
from scraper import parse_schedules, parse_thesis_history

class UpdatedLayoutTests(unittest.TestCase):
    def test_schedule_new_layout(self):
        html = '''<table><tr><th>No</th><th>Mahasiswa</th><th>Ujian</th><th>Tempat &amp; Waktu</th><th>Dosen Penguji</th><th>Judul</th></tr><tr><td>1</td><td><strong>Ani</strong><span>12345</span></td><td>sidang</td><td><div>Ruang A</div><div>Hari Jumat, 06 November 2026</div><div>13:00 - 15:00 WITA</div></td><td><li><span>1).</span> Dosen A</li></td><td>Judul</td></tr></table>'''
        result = parse_schedules(html, 'https://example.com/jadwal/2026-11')[0]
        self.assertEqual([result[k] for k in ('nama', 'nim', 'jenis_ujian', 'tanggal_ujian', 'jam_ujian', 'tempat_ruangan')], ['Ani', '12345', 'sidang', 'Hari Jumat, 06 November 2026', '13:00 - 15:00 WITA', 'Ruang A'])
        self.assertEqual(result['penguji_pembimbing'], ['Dosen A'])

    def test_empty_page_is_not_schedule(self):
        self.assertEqual(parse_schedules('<html>Belum ada data</html>', 'https://example.com'), [])

    def test_new_history_layout(self):
        html = '''<div class="list-group-item list-item-clean"><h6>1). Ani <span>(12345)</span></h6><span class="badge-status">penyusunan proposal</span><div><span>Judul Skripsi:</span> Sistem Baru</div><a href="/masuk/riwayat-skripsi/1">Detail Skripsi</a></div>'''
        entry = parse_thesis_history(html, 'https://example.com/masuk/riwayat-skripsi')[0]
        self.assertEqual([entry[k] for k in ('name', 'nim', 'title', 'stage')], ['Ani', '12345', 'Sistem Baru', 'penyusunan proposal'])

if __name__ == '__main__':
    unittest.main()
