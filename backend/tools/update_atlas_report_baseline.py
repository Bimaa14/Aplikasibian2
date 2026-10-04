"""Private, manual-credential helper for the reviewed demo report update."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import uuid

from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.write_concern import WriteConcern

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from lib.workbooks import dataset
from tools.cloud_copy_core import fingerprint, save_snapshot, take_snapshot
from tools.copy_local_to_atlas_demo import atlas_uri, make_client, safe_error, TARGET_NAME
from tools.report_baseline_core import build_report_baseline
from tools.report_baseline_apply import apply_reviewed_baseline, preflight_update, validate_cloud_source

WORKBOOK = ROOT / 'refrensi-spreadsheet/Perkasa Jaya - Store information system (2).xlsx'
EXPECTED_DIGEST = '0a336185b123e856be79801be0e7b354ee5366df1f9eb86056f3fd80bf300061'


def write_status(folder, phase, **metadata):
    temporary = folder / 'status.tmp'
    temporary.write_text(json.dumps({'phase': phase, 'time': datetime.now(timezone.utc).isoformat(),
                                     'target_database': TARGET_NAME, **metadata}, indent=2), encoding='utf-8')
    temporary.replace(folder / 'status.json')


def source_workbook():
    if hashlib.sha256(WORKBOOK.read_bytes()).hexdigest() != EXPECTED_DIGEST:
        raise ValueError('File sheet (2) berubah; minta pemeriksaan ulang sebelum memperbarui laporan.')
    return dataset('store_current', WORKBOOK)


def run_window(folder):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title('Bian - samakan laporan online dengan sheet (2)')
    root.geometry('760x600')
    root.minsize(710, 560)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Perbarui laporan demo online', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
    ttk.Label(frame, text=('Sumber: sheet (2) yang sudah diperiksa\nTujuan: bian_client_demo di Atlas Cluster0\n'
                           'Angka laporan mengikuti sheet. Stok, akun, saldo tagihan, dan riwayat transaksi aplikasi tetap disimpan.'),
              wraplength=700, justify='left').pack(anchor='w', pady=(12, 18))
    ttk.Label(frame, text='Password database Atlas untuk bian_demo_service:').pack(anchor='w')
    password = ttk.Entry(frame, show='*')
    password.pack(fill='x', pady=(6, 8))
    ttk.Label(frame, text='Isi langsung di sini. Password tidak masuk chat, backup, atau log.').pack(anchor='w')
    notice = tk.StringVar(value='1. Isi password lalu klik Cek data online. Server boleh masih menyala saat pengecekan.')
    ttk.Label(frame, textvariable=notice, wraplength=700, justify='left').pack(anchor='w', pady=18)
    controls = ttk.Frame(frame)
    controls.pack(fill='x', pady=(0, 14))
    check_button = ttk.Button(controls, text='Cek data online')
    check_button.pack(side='left')
    apply_button = ttk.Button(controls, text='Perbarui laporan', state='disabled')
    apply_button.pack(side='left', padx=12)
    output = tk.Text(frame, height=10, wrap='word', font=('Segoe UI', 10), state='disabled')
    output.pack(fill='both', expand=True)
    messages = queue.Queue()
    busy = False
    reviewed = None

    def emit(kind, **metadata):
        messages.put((kind, metadata))

    def check_worker(secret):
        try:
            raw = source_workbook()
            with make_client(atlas_uri(secret)) as cloud:
                target = cloud[TARGET_NAME]
                target.command('ping')
                before = take_snapshot(target)
                if fingerprint(before) != fingerprint(take_snapshot(target)):
                    raise ValueError('Data online berubah saat dibaca. Tunggu transaksi selesai lalu cek lagi.')
                validate_cloud_source(before)
                expected, summary = build_report_baseline(before, raw)
                preflight_update(before, expected)
                locked = target.runtime_locks.find_one({'_id': 'financial-writer'}, {'_id': 1}) is not None
            review_folder = folder / ('review-' + uuid.uuid4().hex[:12])
            review_folder.mkdir()
            save_snapshot(before, review_folder / 'atlas-reviewed.ejson')
            save_snapshot(expected, review_folder / 'atlas-expected.ejson')
            write_status(folder, 'reviewed', review_folder=str(review_folder), cloud_locked=locked,
                         reviewed_hash=fingerprint(before), workbook_digest=raw['digest'],
                         excluded_native_transactions=summary['excluded_native_transactions'],
                         excluded_payments=summary['excluded_payments'])
            emit('checked', before=before, expected=expected, summary=summary,
                 review_folder=review_folder, cloud_locked=locked)
        except Exception as error:
            message = safe_error(error)
            write_status(folder, 'check_refused', message=message, error_type=type(error).__name__)
            emit('error', message=message, retained_lock=False, check_failed=True)

    def apply_worker(secret, review):
        owner = 'report-baseline-' + uuid.uuid4().hex
        acquired = False
        attempted = False
        writes_started = False
        verified = False
        cloud = None
        try:
            source_workbook()
            cloud = make_client(atlas_uri(secret))
            target = cloud.get_database(TARGET_NAME, write_concern=WriteConcern(w='majority', j=True, wtimeout=10000))
            target.command('ping')
            locks = target.runtime_locks
            attempted = True
            # A stopped Railway process releases its own lock. Never clear somebody else's lock.
            locks.insert_one({'_id': 'financial-writer', 'owner': owner,
                              'started_at': datetime.now(timezone.utc), 'purpose': 'report-baseline-update'})
            acquired = True
            current = take_snapshot(target)
            if fingerprint(current) != fingerprint(review['before']):
                raise ValueError('Data online berubah setelah pengecekan. Klik Cek data online lagi.')
            preflight_update(current, review['expected'])
            save_snapshot(current, review['review_folder'] / 'atlas-before-update.ejson')
            write_status(folder, 'updating', transfer_owner=owner, review_folder=str(review['review_folder']))
            emit('progress', text='Backup tersimpan dan kunci diperoleh. Memperbarui laporan lalu memeriksa seluruh data...')
            writes_started = True
            result = apply_reviewed_baseline(current, review['expected'], target, required_owner=owner)
            verified = True
            write_status(folder, 'verified', transfer_owner=owner, **result)
            if locks.delete_one({'_id': 'financial-writer', 'owner': owner}).deleted_count != 1:
                raise RuntimeError('Data sesuai, tetapi pelepasan kunci perlu diperiksa dahulu.')
            acquired = False
            write_status(folder, 'complete', workbook_digest=EXPECTED_DIGEST, **result)
            emit('complete', counts=result['counts'])
        except Exception as error:
            retained = acquired or (attempted and not isinstance(error, DuplicateKeyError))
            if acquired and not writes_started and cloud is not None:
                try:
                    retained = cloud[TARGET_NAME].runtime_locks.with_options(
                        write_concern=WriteConcern(w='majority', j=True, wtimeout=10000)
                    ).delete_one({'_id': 'financial-writer', 'owner': owner}).deleted_count != 1
                except PyMongoError:
                    retained = True
            message = safe_error(error)
            write_status(folder, 'verified_lock_check' if verified else ('update_failed_held' if retained else 'update_refused'),
                         message=message, error_type=type(error).__name__, retained_lock=retained,
                         transfer_owner=owner if retained else None)
            emit('error', message=message, retained_lock=retained, check_failed=False)
        finally:
            if cloud is not None:
                cloud.close()

    def start(action):
        nonlocal busy
        if busy:
            return
        secret = password.get()
        if not secret:
            notice.set('Isi password database Atlas terlebih dahulu.')
            return
        if action == 'apply' and reviewed is None:
            notice.set('Klik Cek data online terlebih dahulu.')
            return
        busy = True
        password.configure(state='disabled')
        check_button.configure(state='disabled')
        apply_button.configure(state='disabled')
        notice.set('Memeriksa data online...' if action == 'check' else 'Memperbarui laporan. Biarkan jendela ini tetap terbuka.')
        threading.Thread(target=check_worker if action == 'check' else apply_worker,
                         args=(secret,) if action == 'check' else (secret, reviewed), daemon=False).start()

    def add_line(value):
        output.configure(state='normal')
        output.insert('end', value + '\n')
        output.see('end')
        output.configure(state='disabled')

    def poll():
        nonlocal busy, reviewed
        try:
            while True:
                kind, data = messages.get_nowait()
                if kind == 'progress':
                    add_line(data['text'])
                    continue
                busy = False
                if kind == 'checked':
                    reviewed = data
                    password.configure(state='normal')
                    check_button.configure(state='normal')
                    apply_button.configure(state='normal')
                    notice.set('2. Hentikan deployment aktif di Railway. Setelah Offline, klik Perbarui laporan.')
                    add_line('Rencana September: pendapatan Rp399.283.000; laba bersih Rp3.543.000.')
                    add_line(f"{data['summary']['excluded_native_transactions']} transaksi aplikasi tetap disimpan dan dikecualikan dari baseline sheet.")
                    add_line('Server masih memegang kunci.' if data['cloud_locked'] else 'Kunci database saat ini bebas.')
                elif kind == 'complete':
                    password.configure(state='normal')
                    password.delete(0, 'end')
                    password.configure(state='disabled')
                    notice.set('Selesai! Data online sudah diverifikasi. Jalankan deployment kode terbaru yang memakai sheet (2).')
                    add_line('Stok, akun, dan saldo tagihan tetap sesuai sebelum pembaruan. Backup tersimpan.')
                elif kind == 'error':
                    notice.set(data['message'])
                    add_line(data['message'])
                    password.configure(state='normal')
                    if data['check_failed']:
                        reviewed = None
                    if data['retained_lock']:
                        password.delete(0, 'end')
                        password.configure(state='disabled')
                        add_line('Kunci dipertahankan untuk pemeriksaan. Kabari Codex sebelum menjalankan web kembali.')
                    else:
                        check_button.configure(state='normal')
                        apply_button.configure(state='normal' if reviewed is not None else 'disabled')
        except queue.Empty:
            pass
        root.after(200, poll)

    def close():
        if busy:
            notice.set('Tunggu proses selesai sebelum menutup jendela ini.')
        else:
            root.destroy()

    check_button.configure(command=lambda: start('check'))
    apply_button.configure(command=lambda: start('apply'))
    root.protocol('WM_DELETE_WINDOW', close)
    root.after_idle(lambda: write_status(folder, 'waiting_for_atlas_password'))
    root.after(200, poll)
    password.focus_set()
    root.mainloop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    args = parser.parse_args()
    destination = Path(args.folder).resolve()
    allowed = (ROOT / '.cache/report-baseline').resolve()
    if destination == allowed or not destination.is_relative_to(allowed) or destination.exists():
        raise ValueError('Use a new private folder inside .cache/report-baseline.')
    destination.mkdir(parents=True)
    run_window(destination)
