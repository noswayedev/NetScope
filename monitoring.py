"""Local-only monitoring dashboard, persistent snapshots and non-blocking UI charts."""
from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
import csv
import ipaddress
import sqlite3
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import psutil

BG = '#0b111c'
PANEL = '#121c2b'
PANEL2 = '#192638'
ACCENT = '#51e1c1'
TEXT = '#eaf4ff'
MUTED = '#91a5bc'
BORDER = '#2a3d51'


def database_path():
    from os import getenv
    return Path(getenv('APPDATA') or (Path.home() / '.config')) / 'NetScope' / 'history.sqlite3'


class HistoryStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY, at TEXT NOT NULL, network TEXT NOT NULL, count INTEGER NOT NULL, duration_s REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sightings (scan_id INTEGER NOT NULL, ip TEXT NOT NULL, mac TEXT NOT NULL, latency_ms REAL, FOREIGN KEY(scan_id) REFERENCES scans(id))')
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at TEXT NOT NULL, network TEXT NOT NULL, kind TEXT NOT NULL, ip TEXT NOT NULL, details TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS ix_scan_network ON scans(network, id)')
            db.execute('CREATE INDEX IF NOT EXISTS ix_events_network ON events(network, id)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=4)

    def last_hosts(self, network):
        with self.connect() as db:
            row = db.execute('SELECT id FROM scans WHERE network=? ORDER BY id DESC LIMIT 1', (network,)).fetchone()
            if not row:
                return None
            return {ip: mac for ip, mac in db.execute('SELECT ip, mac FROM sightings WHERE scan_id=?', (row[0],))}

    def record_scan(self, network, hosts, duration):
        now = datetime.now().astimezone().isoformat(timespec='seconds')
        previous = self.last_hosts(network)
        current = {ip: host.mac for ip, host in hosts.items()}
        changes = []
        if previous is not None:
            for ip in sorted(current.keys() - previous.keys(), key=ipaddress.ip_address):
                changes.append(('new', ip, current[ip]))
            for ip in sorted(previous.keys() - current.keys(), key=ipaddress.ip_address):
                changes.append(('missing', ip, previous[ip]))
        with self.connect() as db:
            scan_id = db.execute('INSERT INTO scans(at, network, count, duration_s) VALUES (?,?,?,?)',
                                 (now, network, len(hosts), duration)).lastrowid
            db.executemany('INSERT INTO sightings(scan_id, ip, mac, latency_ms) VALUES (?,?,?,?)',
                           ((scan_id, h.ip, h.mac, h.latency_ms) for h in hosts.values()))
            db.executemany('INSERT INTO events(at, network, kind, ip, details) VALUES (?,?,?,?,?)',
                           ((now, network, kind, ip, details) for kind, ip, details in changes))
        return changes, previous is not None

    def events(self, limit=150):
        with self.connect() as db:
            return db.execute('SELECT at, kind, ip, network, details FROM events ORDER BY id DESC LIMIT ?', (limit,)).fetchall()

    def scans(self, limit=100):
        with self.connect() as db:
            return db.execute('SELECT at, network, count, duration_s FROM scans ORDER BY id DESC LIMIT ?', (limit,)).fetchall()

    def clear(self):
        with self.connect() as db:
            db.execute('DELETE FROM sightings')
            db.execute('DELETE FROM events')
            db.execute('DELETE FROM scans')


class MonitorMixin:
    def init_monitor(self):
        self.monitor_enabled = False
        self.monitor_next = None
        self.scan_network = None
        self.scan_is_monitor = False
        self.traffic_samples = deque(maxlen=90)
        self.latency_samples = deque(maxlen=90)
        self.previous_counters = None
        self.previous_counter_time = None
        self.history = None
        try:
            self.history = HistoryStore()
        except (OSError, sqlite3.Error) as exc:
            self.log(f'History storage unavailable: {exc}', 'error')
        self.root.after(1000, self.monitor_tick)

    def build_monitor_tab(self):
        tab = self.monitor_tab
        bar = self.section(tab, self.t('monitor_title'))
        row = tk.Frame(bar, bg=PANEL)
        row.pack(fill='x')
        self.monitor_status_var = tk.StringVar(value=self.t('monitor_off'))
        self.label(row, self.t('interval'), 10, MUTED).pack(side='left', padx=(0, 8))
        self.interval_var = tk.StringVar(value=str(self.prefs['monitor_interval']))
        tk.Spinbox(row, from_=30, to=3600, increment=15, textvariable=self.interval_var,
                   bg=PANEL2, fg=TEXT, buttonbackground=PANEL2, relief='flat', width=7,
                   font=('Segoe UI', 11)).pack(side='left', padx=(0, 12))
        self.monitor_start_btn = self.button(row, self.t('monitor_start'), self.start_monitor, True, 16)
        self.monitor_start_btn.pack(side='left', padx=(0, 8))
        self.monitor_stop_btn = self.button(row, self.t('monitor_stop'), self.stop_monitor, width=16)
        self.monitor_stop_btn.pack(side='left')
        self.label(bar, self.t('monitor_note'), 9, MUTED, wraplength=1100, justify='left').pack(anchor='w', pady=(10, 0))
        self.label(bar, '', 10, MUTED, textvariable=self.monitor_status_var).pack(anchor='w', pady=(5, 0))

        cards = tk.Frame(tab, bg=BG)
        cards.pack(fill='x', pady=(0, 10))
        self.rate_down_var = tk.StringVar(value='—')
        self.rate_up_var = tk.StringVar(value='—')
        self.connections_var = tk.StringVar(value='—')
        for i, (label, var) in enumerate((('download', self.rate_down_var), ('upload', self.rate_up_var), ('connections_count', self.connections_var))):
            card = tk.Frame(cards, bg=PANEL, padx=14, pady=7, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=i, sticky='ew', padx=(0, 9 if i < 2 else 0))
            cards.columnconfigure(i, weight=1)
            self.label(card, self.t(label), 9, MUTED, True).pack(anchor='w')
            tk.Label(card, textvariable=var, bg=PANEL, fg=ACCENT, font=('Segoe UI Semibold', 17)).pack(anchor='w')

        charts = tk.Frame(tab, bg=BG)
        charts.pack(fill='both', expand=True)
        charts.columnconfigure(0, weight=1)
        charts.columnconfigure(1, weight=1)
        charts.rowconfigure(0, weight=1)
        for col, (key, attr) in enumerate((('traffic_chart', 'traffic_canvas'), ('latency_chart', 'latency_canvas'))):
            box = tk.Frame(charts, bg=PANEL, padx=12, pady=9, highlightbackground=BORDER, highlightthickness=1)
            box.grid(row=0, column=col, sticky='nsew', padx=(0, 5) if col == 0 else (5, 0))
            self.label(box, self.t(key), 10, TEXT, True).pack(anchor='w')
            canvas = tk.Canvas(box, bg='#0d1623', highlightthickness=0, height=135)
            canvas.pack(fill='both', expand=True, pady=(5, 0))
            setattr(self, attr, canvas)
            canvas.bind('<Configure>', lambda _e: self.draw_charts())

        foot = tk.Frame(tab, bg=BG)
        foot.pack(fill='both', expand=True, pady=(10, 2))
        self.label(foot, self.t('local_connections'), 11, TEXT, True).pack(anchor='w', pady=(0, 5))
        cols = ('remote', 'count')
        self.conn_tree = ttk.Treeview(foot, columns=cols, show='headings', height=4, style='App.Treeview')
        self.conn_tree.heading('remote', text=self.t('remote_endpoint'))
        self.conn_tree.heading('count', text=self.t('connections_count'))
        self.conn_tree.column('remote', width=300)
        self.conn_tree.column('count', width=120)
        self.conn_tree.pack(fill='both', expand=True)
        self.refresh_monitor_buttons()
        self.draw_charts()

    def build_history_tab(self):
        tab = self.history_tab
        toolbar = tk.Frame(tab, bg=BG, pady=9)
        toolbar.pack(fill='x')
        self.label(toolbar, self.t('history_title'), 13, TEXT, True).pack(side='left')
        self.button(toolbar, self.t('clear_history'), self.clear_history, width=15).pack(side='right')
        self.button(toolbar, self.t('export_history'), self.export_history, width=16).pack(side='right', padx=9)
        self.button(toolbar, self.t('refresh'), self.refresh_history, width=12).pack(side='right')
        self.label(tab, self.t('history_note'), 9, MUTED, wraplength=1100, justify='left').pack(anchor='w', pady=(0, 9))
        area = tk.Frame(tab, bg=BG)
        area.pack(fill='both', expand=True)
        self.label(area, self.t('recent_events'), 11, ACCENT, True).pack(anchor='w', pady=(0, 4))
        cols = ('at', 'kind', 'ip', 'network')
        self.event_tree = ttk.Treeview(area, columns=cols, show='headings', height=8, style='App.Treeview')
        for col, label, width in zip(cols, ('date', 'event_type', 'ip', 'network'), (190, 160, 190, 190)):
            self.event_tree.heading(col, text=self.t(label))
            self.event_tree.column(col, width=width)
        self.event_tree.pack(fill='both', expand=True, pady=(0, 11))
        self.label(area, self.t('recent_scans'), 11, ACCENT, True).pack(anchor='w', pady=(0, 4))
        cols = ('at', 'network', 'count', 'duration')
        self.scan_history_tree = ttk.Treeview(area, columns=cols, show='headings', height=6, style='App.Treeview')
        for col, label, width in zip(cols, ('date', 'network', 'found', 'duration'), (190, 190, 130, 120)):
            self.scan_history_tree.heading(col, text=self.t(label))
            self.scan_history_tree.column(col, width=width)
        self.scan_history_tree.pack(fill='both', expand=True)
        self.refresh_history()

    def refresh_history(self):
        if not self.history:
            return
        try:
            if hasattr(self, 'event_tree') and self.event_tree.winfo_exists():
                self.event_tree.delete(*self.event_tree.get_children())
                for at, kind, ip, network, _details in self.history.events():
                    self.event_tree.insert('', 'end', values=(at.replace('T', ' ')[:19], self.t('event_' + kind), ip, network))
            if hasattr(self, 'scan_history_tree') and self.scan_history_tree.winfo_exists():
                self.scan_history_tree.delete(*self.scan_history_tree.get_children())
                for at, network, count, duration in self.history.scans():
                    self.scan_history_tree.insert('', 'end', values=(at.replace('T', ' ')[:19], network, count, f'{duration:.1f}s'))
        except sqlite3.Error as exc:
            self.log(f'History read error: {exc}', 'error')

    def export_history(self):
        if not self.history:
            return
        filename = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')],
                                               initialfile='netscope-history.csv')
        if not filename:
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(('date', 'event', 'ip', 'network', 'details'))
                writer.writerows(self.history.events(100000))
            self.log(f'HISTORY EXPORTED {filename}', 'success')
        except (OSError, sqlite3.Error) as exc:
            messagebox.showerror(self.t('error'), str(exc))

    def clear_history(self):
        if not self.history:
            return
        if not messagebox.askyesno(self.t('warn_title'), self.t('clear_history_confirm')):
            return
        try:
            self.history.clear()
            self.refresh_history()
            self.log('History cleared', 'success')
        except sqlite3.Error as exc:
            self.log(f'History clear error: {exc}', 'error')

    def refresh_monitor_buttons(self):
        if not hasattr(self, 'monitor_start_btn'):
            return
        self.monitor_start_btn.configure(state='disabled' if self.monitor_enabled else 'normal')
        self.monitor_stop_btn.configure(state='normal' if self.monitor_enabled else 'disabled')
        if self.monitor_enabled:
            status = self.t('monitor_running')
            if self.scan_active:
                status += ' • ' + self.t('scan_active')
            elif self.monitor_next is not None:
                status += f' • {max(0, int(self.monitor_next - time.monotonic()))}s'
        else:
            status = self.t('monitor_off')
        if hasattr(self, 'monitor_status_var'):
            self.monitor_status_var.set(status)

    def start_monitor(self):
        if self.scan_active:
            messagebox.showinfo(self.t('warn_title'), self.t('scan_active'))
            return
        if self.network_var.get() not in self.interface_map:
            messagebox.showwarning(self.t('warn_title'), self.t('choose_interface'))
            return
        try:
            interval = int(self.interval_var.get())
            if not 30 <= interval <= 3600:
                raise ValueError
        except ValueError:
            messagebox.showerror(self.t('error'), self.t('interval_error'))
            return
        import ipaddress
        network = ipaddress.ip_network(self.interface_map[self.network_var.get()], strict=False)
        if network.num_addresses > 256:
            messagebox.showwarning(self.t('warn_title'), self.t('too_large'))
            return
        if not messagebox.askyesno(self.t('authorized_title'), self.t('monitor_permission', network=network, interval=interval)):
            return
        self.prefs['monitor_interval'] = interval
        self.save_settings_file()
        self.monitor_enabled = True
        self.monitor_network_label = self.network_var.get()
        self.monitor_network = str(network)
        self.monitor_next = time.monotonic()
        self.refresh_monitor_buttons()
        self.log(f'MONITOR START {network} • every {interval}s', 'success')
        self.monitor_maybe_scan()

    def stop_monitor(self):
        self.monitor_enabled = False
        self.monitor_next = None
        self.refresh_monitor_buttons()
        self.log('MONITOR STOPPED')

    def monitor_maybe_scan(self):
        if not self.monitor_enabled or self.scan_active:
            return
        if self.monitor_next is None or time.monotonic() < self.monitor_next:
            return
        if self.network_var.get() != self.monitor_network_label:
            self.log('Monitor stopped: network interface selection changed', 'error')
            self.stop_monitor()
            return
        self.start_scan(automated=True)

    def on_scan_snapshot(self, stopped, duration):
        network = self.scan_network
        if not stopped and network and self.history:
            try:
                changes, baseline = self.history.record_scan(network, self.hosts, duration)
                self.refresh_history()
                valid_lats = [h.latency_ms for h in self.hosts.values() if h.latency_ms is not None]
                if valid_lats:
                    self.latency_samples.append(sum(valid_lats) / len(valid_lats))
                for index, (kind, ip, _mac) in enumerate(changes):
                    msg = f'{self.t("event_" + kind)}: {ip} ({network})'
                    self.log('ALERT ' + msg, 'success' if kind == 'new' else 'error')
                    if self.prefs['monitor_alerts'] and self.monitor_enabled and index < 3:
                        self.show_monitor_alert(msg)
                if len(changes) > 3 and self.prefs['monitor_alerts'] and self.monitor_enabled:
                    self.show_monitor_alert(f'{len(changes)} changes detected • see History')
                if not baseline:
                    self.log('MONITOR BASELINE saved • no change alerts on first scan')
            except (sqlite3.Error, OSError) as exc:
                self.log(f'History write error: {exc}', 'error')
        if self.monitor_enabled:
            self.monitor_next = time.monotonic() + self.prefs['monitor_interval']
            self.refresh_monitor_buttons()

    def show_monitor_alert(self, message):
        # Non-blocking in-app notification (does not require external services).
        if not self.root.winfo_exists():
            return
        toast = tk.Toplevel(self.root)
        toast.title('NetScope')
        toast.configure(bg=PANEL2)
        toast.resizable(False, False)
        toast.attributes('-topmost', True)
        toast.geometry('410x90+30+30')
        self.label(toast, '◈  NetScope', 11, ACCENT, True).pack(anchor='w', padx=15, pady=(9, 2))
        self.label(toast, message, 10, TEXT, wraplength=380, justify='left').pack(anchor='w', padx=15)
        toast.after(4500, lambda: toast.destroy() if toast.winfo_exists() else None)
        self.root.bell()

    def monitor_tick(self):
        if not self.root.winfo_exists():
            return
        try:
            now = time.monotonic()
            counters = psutil.net_io_counters()
            if counters and self.previous_counters and self.previous_counter_time:
                dt = max(0.01, now - self.previous_counter_time)
                down = max(0, counters.bytes_recv - self.previous_counters.bytes_recv) / dt
                up = max(0, counters.bytes_sent - self.previous_counters.bytes_sent) / dt
                self.traffic_samples.append((down, up))
                if hasattr(self, 'rate_down_var'):
                    self.rate_down_var.set(self.human_rate(down))
                    self.rate_up_var.set(self.human_rate(up))
            self.previous_counters = counters
            self.previous_counter_time = now
            self.draw_charts()
            if hasattr(self, 'conn_tree') and self.conn_tree.winfo_exists() and int(now) % 5 == 0:
                self.refresh_connections()
        except (OSError, psutil.Error, tk.TclError) as exc:
            # Continue the periodic UI loop even without access to socket info.
            self.log(f'MONITOR sampling unavailable: {exc}', 'dim')
        self.monitor_maybe_scan()
        self.refresh_monitor_buttons()
        self.root.after(1000, self.monitor_tick)

    @staticmethod
    def human_rate(bps):
        for unit in ('B/s', 'KB/s', 'MB/s', 'GB/s'):
            if bps < 1024:
                return f'{bps:.1f} {unit}'
            bps /= 1024
        return f'{bps:.1f} TB/s'

    def refresh_connections(self):
        # Only sockets from this computer; not packet sniffing or remote-host discovery.
        try:
            all_conns = psutil.net_connections(kind='inet')
        except (psutil.Error, OSError):
            self.connections_var.set(self.t('permission_needed'))
            return
        counter = {}
        for conn in all_conns:
            if conn.raddr and conn.status == 'ESTABLISHED':
                host = conn.raddr.ip
                counter[host] = counter.get(host, 0) + 1
        self.connections_var.set(str(sum(counter.values())))
        self.conn_tree.delete(*self.conn_tree.get_children())
        for host, number in sorted(counter.items(), key=lambda item: -item[1])[:15]:
            self.conn_tree.insert('', 'end', values=(host, number))

    def draw_charts(self):
        if hasattr(self, 'traffic_canvas') and self.traffic_canvas.winfo_exists():
            samples = list(self.traffic_samples)
            self.draw_chart(self.traffic_canvas, [v[0] / 1024 for v in samples], '#51e1c1',
                            [v[1] / 1024 for v in samples], '#78a9ff', 'KB/s')
        if hasattr(self, 'latency_canvas') and self.latency_canvas.winfo_exists():
            self.draw_chart(self.latency_canvas, list(self.latency_samples), '#f5ca81', unit='ms')

    @staticmethod
    def draw_chart(canvas, series, color, second=None, second_color=None, unit=''):
        canvas.delete('all')
        w = max(60, canvas.winfo_width())
        h = max(60, canvas.winfo_height())
        left, right, top, bottom = 48, w - 12, 15, h - 25
        if right <= left:
            return
        maxvalue = max([1.0] + series + (second or [])) * 1.15
        for i in range(4):
            y = top + (bottom - top) * i / 3
            canvas.create_line(left, y, right, y, fill='#253449', dash=(3, 5))
            canvas.create_text(left - 5, y, text=f'{maxvalue * (3-i)/3:.0f}', anchor='e', fill=MUTED, font=('Segoe UI', 8))
        canvas.create_text(right, h - 10, text=unit, anchor='e', fill=MUTED, font=('Segoe UI', 8))
        def plot(values, stroke):
            if not values:
                return
            x_step = (right - left) / max(1, len(values) - 1)
            pts = []
            for i, value in enumerate(values):
                pts.extend([left + i * x_step, bottom - (value / maxvalue) * (bottom - top)])
            if len(pts) >= 4:
                canvas.create_line(*pts, fill=stroke, width=2, smooth=False)
            else:
                canvas.create_oval(pts[0]-2, pts[1]-2, pts[0]+2, pts[1]+2, fill=stroke, outline='')
        plot(series, color)
        if second is not None:
            plot(second, second_color)
            canvas.create_text(left + 5, bottom - 7, text='↓ download  ↑ upload', fill=MUTED,
                               anchor='sw', font=('Segoe UI', 8))
