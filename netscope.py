"""NetScope — local network discovery and diagnostics.

Only intended for networks you own or have permission to test.
No data leaves the machine; no telemetry or third-party services.
"""
from __future__ import annotations

import csv
import ipaddress
import json
import os
import platform
import queue
import re
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
import sys
from tkinter import filedialog, messagebox, ttk
from translations import LANGUAGES, translate
from diagnostics_extra import TOOL_DEFS, TOOL_TRANSLATIONS, run_extra_tool, needs_target
from monitoring import MonitorMixin

import psutil

APP_TITLE = "NetScope"
VERSION = "4.0.0"
BG = "#0b111c"
PANEL = "#121c2b"
PANEL2 = "#192638"
ACCENT = "#51e1c1"
TEXT = "#eaf4ff"
MUTED = "#91a5bc"
BORDER = "#2a3d51"
COMMON_PORTS = {
    21: "FTP", 22: "SSH", 53: "DNS", 80: "HTTP", 139: "NetBIOS",
    443: "HTTPS", 445: "SMB", 3389: "RDP", 5900: "VNC", 8080: "HTTP alt",
}


@dataclass
class Host:
    ip: str
    hostname: str = "—"
    mac: str = "—"
    latency_ms: float | None = None
    open_ports: str = "Not checked"


def allowed_network(network: ipaddress.IPv4Network) -> bool:
    """Constrain automated discovery to private RFC1918 networks."""
    private_blocks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    )
    return any(network.subnet_of(block) for block in private_blocks)


def get_interfaces() -> list[tuple[str, str, str]]:
    result = []
    stats = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        if name in stats and not stats[name].isup:
            continue
        for addr in addresses:
            if addr.family != socket.AF_INET or not addr.netmask:
                continue
            try:
                network = ipaddress.IPv4Network(f"{addr.address}/{addr.netmask}", strict=False)
            except ValueError:
                continue
            if allowed_network(network):
                result.append((name, addr.address, str(network)))
    return sorted(result, key=lambda item: (item[1].startswith("169.254"), item[0].lower()))


def ping_host(ip: str, timeout_ms: int = 650) -> float | None:
    """One ICMP echo; None means no confirmed response."""
    is_windows = os.name == "nt"
    cmd = (["ping", "-n", "1", "-w", str(timeout_ms), ip] if is_windows else
           ["ping", "-c", "1", "-W", "1", ip])
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0:
            elapsed = (time.monotonic() - start) * 1000
            # Measured wall-clock RTT approximation, not parsed OS-specific ping output.
            return round(elapsed, 1)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def read_arp_table() -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["arp", "-a" if os.name == "nt" else "-an"],
            capture_output=True, text=True, errors="replace", timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    table: dict[str, str] = {}
    # Windows: 192.168.1.1  aa-bb-cc-dd-ee-ff  dynamic
    for ip, mac in re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})\b", proc.stdout):
        table[ip] = mac.upper().replace("-", ":")
    # Linux: ? (192.168.1.1) at 00:11:22:33:44:55 [ether] on eth0
    for ip, mac in re.findall(r"\((\d{1,3}(?:\.\d{1,3}){3})\)\s+at\s+([0-9a-fA-F:]{17})", proc.stdout):
        table[ip] = mac.upper()
    return table


def reverse_hostname(ip: str) -> str:
    try:
        # Use the system DNS resolver; reverse DNS may be missing for many LAN devices.
        return socket.gethostbyaddr(ip)[0]
    except (OSError, socket.herror, socket.gaierror):
        return "—"


def check_ports(ip: str, ports: dict[int, str] = COMMON_PORTS) -> str:
    found = []
    for port, service in ports.items():
        try:
            with socket.create_connection((ip, port), timeout=0.25):
                found.append(f"{port} ({service})")
        except OSError:
            pass
    return ", ".join(found) if found else "None detected"



DEFAULTS = {
    "language": "fr", "timeout": 650, "workers": 24, "dns": False,
    "arp": True, "show_misses": False, "confirm": True,
    "timestamps": True, "autoscroll": True, "log_detail": "normal",
    "monitor_interval": 60, "monitor_alerts": True,
}


def settings_path() -> Path:
    base = Path(os.getenv("APPDATA") or (Path.home() / ".config"))
    return base / "NetScope" / "settings.json"


def load_settings() -> dict:
    result = DEFAULTS.copy()
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in result:
                if key in data and type(data[key]) is type(result[key]):
                    result[key] = data[key]
    except (OSError, ValueError):
        pass
    result['timeout'] = max(100, min(2000, result['timeout']))
    result['workers'] = max(1, min(64, result['workers']))
    result['monitor_interval'] = max(30, min(3600, result['monitor_interval']))
    if result['language'] not in LANGUAGES:
        result['language'] = 'en'
    return result



# First-launch language selection. Each entry is translated in its own language.
WELCOME_COPY = {
    'en': ('WELCOME TO NETSCOPE', 'Choose your language', 'You can change it later in Settings.', 'Continue'),
    'fr': ('BIENVENUE SUR NETSCOPE', 'Choisissez votre langue', 'Vous pourrez la modifier dans les paramètres.', 'Continuer'),
    'de': ('WILLKOMMEN BEI NETSCOPE', 'Wähle deine Sprache', 'Du kannst sie später in den Einstellungen ändern.', 'Weiter'),
    'es': ('BIENVENIDO A NETSCOPE', 'Elige tu idioma', 'Puedes cambiarlo más tarde en Ajustes.', 'Continuar'),
    'it': ('BENVENUTO IN NETSCOPE', 'Scegli la tua lingua', 'Puoi cambiarla in seguito nelle impostazioni.', 'Continua'),
    'ja': ('NETSCOPE へようこそ', '言語を選択してください', '後から設定で変更できます。', '続行'),
    'ko': ('NETSCOPE에 오신 것을 환영합니다', '언어를 선택하세요', '나중에 설정에서 변경할 수 있습니다.', '계속'),
    'pt': ('BEM-VINDO AO NETSCOPE', 'Escolha seu idioma', 'Você pode alterá-lo depois nas Configurações.', 'Continuar'),
    'ru': ('ДОБРО ПОЖАЛОВАТЬ В NETSCOPE', 'Выберите язык', 'Позже язык можно изменить в настройках.', 'Продолжить'),
    'zh': ('欢迎使用 NETSCOPE', '请选择语言', '以后可以在设置中更改。', '继续'),
}


def first_launch_language(root: tk.Tk) -> bool:
    """Show a language picker once, then atomically persist the initial choice.

    Returning False means the user closed the welcome screen without starting.
    Existing installs with a settings file skip the welcome screen.
    """
    path = settings_path()
    if path.is_file():
        return True

    chosen = {'accepted': False}
    dlg = tk.Toplevel(root)
    dlg.title('NetScope • Welcome / Bienvenue')
    apply_icon(dlg)
    dlg.configure(bg=BG)
    dlg.geometry('555x565')
    dlg.resizable(False, False)
    dlg.protocol('WM_DELETE_WINDOW', dlg.destroy)
    dlg.grab_set()
    dlg.update_idletasks()
    x = max(0, (dlg.winfo_screenwidth() - 555) // 2)
    y = max(0, (dlg.winfo_screenheight() - 565) // 2)
    dlg.geometry(f'+{x}+{y}')

    content = tk.Frame(dlg, bg=BG, padx=36, pady=28)
    content.pack(fill='both', expand=True)
    tk.Label(content, text='◈  NETSCOPE', bg=BG, fg=ACCENT,
             font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=(0, 20))
    heading = tk.Label(content, bg=BG, fg=TEXT, font=('Segoe UI', 15, 'bold'))
    heading.pack(anchor='w', pady=(0, 7))
    subtitle = tk.Label(content, bg=BG, fg=MUTED, font=('Segoe UI', 11))
    subtitle.pack(anchor='w', pady=(0, 15))

    # Show all languages in their native script. Default to French.
    lang_var = tk.StringVar(value=LANGUAGES['fr'])
    choices = tk.Frame(content, bg=PANEL)
    choices.pack(fill='both', expand=True)
    for code, name in LANGUAGES.items():
        tk.Radiobutton(choices, text=name, value=name, variable=lang_var,
                       command=lambda: refresh(), bg=PANEL, fg=TEXT,
                       activebackground=PANEL2, activeforeground=TEXT,
                       selectcolor=PANEL2, anchor='w',
                       font=('Segoe UI', 10), padx=15, pady=3,
                       indicatoron=True, highlightthickness=0).pack(fill='x')

    note = tk.Label(content, bg=BG, fg=MUTED, font=('Segoe UI', 9))
    note.pack(anchor='w', pady=(17, 11))

    def accept():
        language = next((c for c, name in LANGUAGES.items() if name == lang_var.get()), 'fr')
        prefs = DEFAULTS.copy()
        prefs['language'] = language
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding='utf-8')
            tmp.replace(path)
        except OSError as exc:
            messagebox.showerror('NetScope', str(exc), parent=dlg)
            return
        chosen['accepted'] = True
        dlg.destroy()

    button = tk.Button(content, command=accept, bg=ACCENT, fg=BG,
                       activebackground='#89f4dc', activeforeground=BG,
                       font=('Segoe UI', 11, 'bold'), relief='flat', cursor='hand2',
                       padx=20, pady=10)
    button.pack(fill='x')

    def refresh():
        code = next((c for c, name in LANGUAGES.items() if name == lang_var.get()), 'fr')
        welcome, title, hint, action = WELCOME_COPY[code]
        heading.configure(text=welcome)
        subtitle.configure(text=title)
        note.configure(text=hint)
        button.configure(text=action + '  →')

    refresh()
    dlg.bind('<Return>', lambda _event: accept())
    root.wait_window(dlg)
    return chosen['accepted']


def apply_icon(window):
    """Use the packaged PNG for the titlebar/taskbar when Tk supports it."""
    try:
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        asset = base / 'assets' / 'netscope.png'
        icon = tk.PhotoImage(file=str(asset))
        window.iconphoto(True, icon)
        window._netscope_icon = icon
    except (OSError, tk.TclError):
        pass


class NetScopeApp(MonitorMixin):
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_TITLE} • v{VERSION}")
        apply_icon(self.root)
        self.root.geometry('1230x810')
        self.root.minsize(950, 665)
        self.root.configure(bg=BG)
        self.prefs = load_settings()
        self.events: queue.Queue[tuple] = queue.Queue()
        self.stop_event = threading.Event()
        self.scan_active = False
        self.diagnostic_active = False
        self.hosts: dict[str, Host] = {}
        self.interface_map: dict[str, str] = {}
        self.started_at: float | None = None
        self.last_selected_ip: str | None = None
        self.network_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.count_var = tk.StringVar(value='0')
        self.checked_var = tk.StringVar(value='0 / 0')
        self.elapsed_var = tk.StringVar(value='0.0s')
        self.filter_var = tk.StringVar()
        self.console_lines: list[str] = []
        self.make_styles()
        self.init_monitor()
        self.build_ui()
        self.refresh_interfaces()
        self.log(f'NetScope v{VERSION} • Ready • Local-only network diagnostics')
        self.root.after(70, self.process_events)
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

    def t(self, key, **kwargs):
        return translate(self.prefs['language'], key, **kwargs)

    def make_styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('App.TCombobox', fieldbackground=PANEL2, background=PANEL2,
                        foreground=TEXT, arrowcolor=ACCENT, padding=8)
        style.map('App.TCombobox', fieldbackground=[('readonly', PANEL2)],
                  foreground=[('readonly', TEXT)], selectbackground=[('readonly', PANEL2)],
                  selectforeground=[('readonly', TEXT)])
        style.configure('App.Treeview', background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, borderwidth=0, rowheight=36, font=('Segoe UI', 10))
        style.configure('App.Treeview.Heading', background=PANEL2, foreground=MUTED,
                        font=('Segoe UI Semibold', 10), relief='flat', padding=(10, 12))
        style.map('App.Treeview', background=[('selected', '#20544f')], foreground=[('selected', TEXT)])
        style.configure('App.TNotebook', background=BG, borderwidth=0)
        style.configure('App.TNotebook.Tab', background=PANEL, foreground=MUTED,
                        padding=(21, 13), font=('Segoe UI Semibold', 10))
        style.map('App.TNotebook.Tab', background=[('selected', PANEL2)],
                  foreground=[('selected', ACCENT)])
        style.configure('App.Horizontal.TProgressbar', troughcolor=PANEL2, background=ACCENT,
                        bordercolor=PANEL2, lightcolor=ACCENT, darkcolor=ACCENT)

    def label(self, parent, text, size=10, color=TEXT, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color,
                        font=('Segoe UI Semibold' if bold else 'Segoe UI', size), **kw)

    def button(self, parent, text, command, primary=False, width=13):
        return tk.Button(parent, text=text, command=command, width=width,
                         bg=ACCENT if primary else PANEL2, fg=BG if primary else TEXT,
                         activebackground='#80efda' if primary else '#2a3c50',
                         activeforeground=BG if primary else TEXT, relief='flat',
                         font=('Segoe UI Semibold', 10), pady=8, cursor='hand2')

    def section(self, parent, title):
        box = tk.Frame(parent, bg=PANEL, padx=18, pady=14,
                       highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill='x', pady=(0, 14))
        self.label(box, title, 11, ACCENT, True).pack(anchor='w', pady=(0, 10))
        return box

    def build_ui(self, tab_index=0):
        for widget in self.root.winfo_children():
            widget.destroy()
        header = tk.Frame(self.root, bg=BG, padx=28, pady=17)
        header.pack(fill='x')
        row = tk.Frame(header, bg=BG)
        row.pack(fill='x')
        self.label(row, '◈', 24, ACCENT, True).pack(side='left', padx=(0, 10))
        self.label(row, 'NetScope', 25, TEXT, True).pack(side='left')
        self.label(row, f'v{VERSION}  •  {self.t("privacy")}', 9, MUTED).pack(side='right', pady=14)
        self.label(header, self.t('subtitle'), 10, MUTED).pack(anchor='w')

        self.tabs = ttk.Notebook(self.root, style='App.TNotebook')
        self.tabs.pack(fill='both', expand=True, padx=28, pady=(0, 8))
        self.devices_tab = tk.Frame(self.tabs, bg=BG)
        self.console_tab = tk.Frame(self.tabs, bg=BG)
        self.tools_tab = tk.Frame(self.tabs, bg=BG)
        self.monitor_tab = tk.Frame(self.tabs, bg=BG)
        self.history_tab = tk.Frame(self.tabs, bg=BG)
        self.settings_tab = tk.Frame(self.tabs, bg=BG)
        for tab, key in [(self.devices_tab, 'devices'), (self.console_tab, 'console'),
                         (self.tools_tab, 'tools'), (self.monitor_tab, 'monitor'),
                         (self.history_tab, 'history'), (self.settings_tab, 'settings')]:
            self.tabs.add(tab, text='  ' + self.t(key) + '  ')
        self.build_devices_tab()
        self.build_console_tab()
        self.build_tools_tab()
        self.build_monitor_tab()
        self.build_history_tab()
        self.build_settings_tab()
        self.tabs.select(tab_index)

        bottom = tk.Frame(self.root, bg=BG, padx=28, pady=12)
        bottom.pack(fill='x')
        self.progress = ttk.Progressbar(bottom, orient='horizontal', mode='determinate',
                                        style='App.Horizontal.TProgressbar')
        self.progress.pack(fill='x', pady=(0, 7))
        tk.Label(bottom, textvariable=self.status_var, bg=BG, fg=MUTED,
                 font=('Segoe UI', 10), anchor='w').pack(fill='x')
        self.render_hosts()
        self.render_console()
        self.apply_busy_state()

    def build_devices_tab(self):
        tab = self.devices_tab
        controls = self.section(tab, self.t('interface'))
        row = tk.Frame(controls, bg=PANEL)
        row.pack(fill='x')
        self.network_combo = ttk.Combobox(row, textvariable=self.network_var, state='readonly',
                                          style='App.TCombobox', width=55)
        self.network_combo.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.refresh_button = self.button(row, self.t('refresh'), self.refresh_interfaces, width=12)
        self.refresh_button.pack(side='left', padx=(0, 8))
        self.scan_button = self.button(row, self.t('start'), self.start_scan, True, width=15)
        self.scan_button.pack(side='left', padx=(0, 8))
        self.stop_button = self.button(row, self.t('stop'), self.stop_scan, width=9)
        self.stop_button.pack(side='left')
        self.label(controls, self.t('scope'), 9, MUTED).pack(anchor='w', pady=(11, 0))

        cards = tk.Frame(tab, bg=BG)
        cards.pack(fill='x', pady=(0, 14))
        for i, (key, var) in enumerate((('found', self.count_var), ('checked', self.checked_var),
                                       ('duration', self.elapsed_var))):
            card = tk.Frame(cards, bg=PANEL, padx=18, pady=11,
                            highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=0, column=i, sticky='ew', padx=(0, 10 if i < 2 else 0))
            cards.columnconfigure(i, weight=1)
            self.label(card, self.t(key), 9, MUTED, True).pack(anchor='w')
            tk.Label(card, textvariable=var, bg=PANEL, fg=ACCENT,
                     font=('Segoe UI Semibold', 23)).pack(anchor='w')

        panel = tk.Frame(tab, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill='both', expand=True, pady=(0, 5))
        head = tk.Frame(panel, bg=PANEL, padx=14, pady=12)
        head.pack(fill='x')
        self.label(head, self.t('discovered'), 13, TEXT, True).pack(side='left')
        self.button(head, self.t('export'), self.export, width=12).pack(side='right')
        self.ports_button = self.button(head, self.t('ports'), self.scan_selected_ports, width=14)
        self.ports_button.pack(side='right', padx=(0, 9))
        search_box = tk.Entry(head, textvariable=self.filter_var, bg=PANEL2, fg=TEXT,
                              insertbackground=TEXT, relief='flat', width=21,
                              font=('Segoe UI', 10))
        search_box.pack(side='right', padx=(0, 10), ipady=8)
        if hasattr(self, '_filter_trace'):
            self.filter_var.trace_remove('write', self._filter_trace)
        self._filter_trace = self.filter_var.trace_add('write', lambda *_: self.render_hosts())
        table_frame = tk.Frame(panel, bg=PANEL)
        table_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        columns = ('ip', 'hostname', 'mac', 'latency', 'ports')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                 selectmode='browse', style='App.Treeview')
        for col, key, width in [('ip','ip',150), ('hostname','hostname',175), ('mac','mac',175),
                                 ('latency','ping',115), ('ports','open_ports',260)]:
            self.tree.heading(col, text=self.t(key), command=lambda c=col: self.sort_by(c))
            self.tree.column(col, minwidth=65, width=width, stretch=True, anchor='w')
        self.tree.tag_configure('odd', background='#162335')
        self.tree.tag_configure('even', background=PANEL)
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<Button-3>', self.context_menu)

    def build_console_tab(self):
        tab = self.console_tab
        line = tk.Frame(tab, bg=BG, pady=12)
        line.pack(fill='x')
        self.label(line, self.t('console_title'), 14, TEXT, True).pack(side='left')
        self.button(line, self.t('save_log'), self.save_log, width=14).pack(side='right')
        self.button(line, self.t('clear_log'), self.clear_log, width=12).pack(side='right', padx=(0, 10))
        self.auto_var = tk.BooleanVar(value=self.prefs['autoscroll'])
        tk.Checkbutton(line, text=self.t('autoscroll'), variable=self.auto_var,
                       bg=BG, fg=MUTED, selectcolor=PANEL2, activebackground=BG,
                       activeforeground=TEXT, command=self.on_auto).pack(side='right', padx=16)
        box = tk.Frame(tab, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill='both', expand=True, pady=(0, 12))
        self.console_text = tk.Text(box, bg='#090f18', fg='#c3e9e1', insertbackground=TEXT,
                                    relief='flat', wrap='word', state='disabled',
                                    font=('Consolas', 10), padx=15, pady=14)
        scrollbar = ttk.Scrollbar(box, command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.console_text.pack(fill='both', expand=True)
        self.console_text.tag_configure('error', foreground='#ff9c9c')
        self.console_text.tag_configure('success', foreground=ACCENT)
        self.console_text.tag_configure('dim', foreground=MUTED)

    def tool_text(self, key):
        lang = self.prefs['language']
        return TOOL_TRANSLATIONS.get(lang, {}).get(key, TOOL_TRANSLATIONS['en'].get(key, key))

    def build_tools_tab(self):
        tab = self.tools_tab
        box = self.section(tab, self.t('test_tools'))
        self.label(box, self.tool_text('intro'), 10, MUTED, wraplength=940,
                   justify='left').pack(anchor='w', pady=(0, 12))
        self.label(box, self.tool_text('target'), 10, MUTED, True).pack(anchor='w')
        self.target_var = tk.StringVar(value=self.last_selected_ip or '')
        tk.Entry(box, textvariable=self.target_var, bg=PANEL2, fg=TEXT,
                 insertbackground=TEXT, relief='flat', font=('Consolas', 12), width=26
                 ).pack(anchor='w', pady=(4, 12), ipady=7)
        self.label(box, self.tool_text('select'), 10, MUTED, True).pack(anchor='w')
        self.tool_var = tk.StringVar()
        self.tool_labels = {}
        for key, category in TOOL_DEFS:
            title = self.tool_text(key)
            label = f'{self.tool_text(category)}  •  {title}'
            self.tool_labels[label] = key
        combo = ttk.Combobox(box, textvariable=self.tool_var,
                             values=list(self.tool_labels), state='readonly',
                             style='App.TCombobox', width=75)
        combo.pack(fill='x', anchor='w', pady=(5, 10))
        combo.current(0)
        self.label(box, self.tool_text('port_hint'), 10, MUTED).pack(anchor='w', pady=(6, 4))
        self.custom_ports_var = tk.StringVar(value=','.join(map(str, COMMON_PORTS)))
        tk.Entry(box, textvariable=self.custom_ports_var, bg=PANEL2, fg=TEXT,
                 insertbackground=TEXT, relief='flat', font=('Consolas', 10), width=65
                 ).pack(anchor='w', ipady=7)
        self.button(box, self.t('run'), self.run_diagnostic, True, width=19
                    ).pack(anchor='w', pady=(12, 2))
        info = self.section(tab, self.tool_text('note_title'))
        self.label(info, self.tool_text('note'), 10, MUTED, wraplength=930,
                   justify='left').pack(anchor='w')

    def build_settings_tab(self):
        outer = tk.Frame(self.settings_tab, bg=BG)
        outer.pack(fill='both', expand=True, pady=10)
        box = self.section(outer, self.t('settings_title'))
        row = tk.Frame(box, bg=PANEL)
        row.pack(anchor='w')
        self.label(row, self.t('language') + '   ', 11).pack(side='left')
        self.lang_var = tk.StringVar(value=LANGUAGES[self.prefs['language']])
        combo = ttk.Combobox(row, values=list(LANGUAGES.values()), textvariable=self.lang_var,
                             state='readonly', style='App.TCombobox', width=25)
        combo.pack(side='left', padx=8)
        combo.bind('<<ComboboxSelected>>', self.change_language)
        self.label(box, self.t('lang_note'), 9, MUTED).pack(anchor='w', pady=(10, 0))
        box = self.section(outer, self.t('scanning'))
        row = tk.Frame(box, bg=PANEL)
        row.pack(anchor='w', pady=(0, 10))
        self.timeout_var = tk.StringVar(value=str(self.prefs['timeout']))
        self.workers_var = tk.StringVar(value=str(self.prefs['workers']))
        for key, var in [('timeout', self.timeout_var), ('workers', self.workers_var)]:
            item = tk.Frame(row, bg=PANEL)
            item.pack(side='left', padx=(0, 30))
            self.label(item, self.t(key), 10, MUTED).pack(anchor='w')
            tk.Spinbox(item, from_=100 if key=='timeout' else 1,
                       to=2000 if key=='timeout' else 64, textvariable=var,
                       bg=PANEL2, fg=TEXT, buttonbackground=PANEL2,
                       relief='flat', width=12, font=('Segoe UI', 11)).pack(anchor='w', pady=7)
        detail_row = tk.Frame(box, bg=PANEL)
        detail_row.pack(anchor='w', pady=(0, 12))
        self.label(detail_row, self.t('log_level') + '   ', 10, MUTED).pack(side='left')
        self.detail_var = tk.StringVar(value=self.t('verbose') if self.prefs['log_detail'] == 'verbose' else self.t('normal'))
        ttk.Combobox(detail_row, values=[self.t('normal'), self.t('verbose')],
                     textvariable=self.detail_var, state='readonly', width=16,
                     style='App.TCombobox').pack(side='left')
        monitor_box = self.section(outer, self.t('monitor_settings'))
        self.monitor_alert_var = tk.BooleanVar(value=self.prefs['monitor_alerts'])
        tk.Checkbutton(monitor_box, text=self.t('monitor_alerts'), variable=self.monitor_alert_var,
                       bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                       activeforeground=TEXT).pack(anchor='w')
        self.flag_vars = {}
        for key in ('dns', 'arp', 'show_misses', 'confirm', 'timestamps'):
            variable = tk.BooleanVar(value=self.prefs[key])
            self.flag_vars[key] = variable
            tk.Checkbutton(box, text=self.t(key), variable=variable, bg=PANEL, fg=TEXT,
                           selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=TEXT).pack(anchor='w', pady=2)
        line = tk.Frame(outer, bg=BG)
        line.pack(fill='x')
        self.button(line, self.t('save'), self.save_settings, True, width=19).pack(side='left')
        self.button(line, self.t('reset'), self.reset_settings, width=20).pack(side='left', padx=12)
        self.label(outer, self.t('version', version=VERSION), 9, MUTED).pack(anchor='w', pady=18)

    def apply_busy_state(self):
        if not hasattr(self, 'scan_button'):
            return
        self.scan_button.config(state='disabled' if self.scan_active else 'normal')
        self.refresh_button.config(state='disabled' if self.scan_active else 'normal')
        self.stop_button.config(state='normal' if self.scan_active and not self.stop_event.is_set() else 'disabled')
        self.network_combo.config(state='disabled' if self.scan_active else 'readonly')
        self.ports_button.config(state='disabled' if self.diagnostic_active else 'normal')

    def change_language(self, _event=None):
        new_lang = next((k for k, v in LANGUAGES.items() if v == self.lang_var.get()), 'en')
        if new_lang == self.prefs['language']:
            return
        try:
            self.capture_settings()
        except ValueError as exc:
            messagebox.showerror(self.t('error'), str(exc))
            return
        self.prefs['language'] = new_lang
        selected = self.tabs.index(self.tabs.select())
        self.build_ui(selected)
        self.save_settings_file()
        self.log('Language changed: ' + LANGUAGES[new_lang])

    def capture_settings(self):
        try:
            timeout = int(self.timeout_var.get())
            workers = int(self.workers_var.get())
            if not 100 <= timeout <= 2000 or not 1 <= workers <= 64:
                raise ValueError('Timeout 100–2000 ms; workers 1–64')
        except ValueError as exc:
            raise ValueError('Ping timeout: 100–2000 ms; workers: 1–64') from exc
        self.prefs['timeout'] = timeout
        self.prefs['workers'] = workers
        for key, var in self.flag_vars.items():
            self.prefs[key] = bool(var.get())
        self.prefs['autoscroll'] = bool(self.auto_var.get())
        self.prefs['monitor_alerts'] = bool(self.monitor_alert_var.get())
        self.prefs['log_detail'] = 'verbose' if self.detail_var.get() == self.t('verbose') else 'normal'

    def save_settings_file(self):
        path = settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.prefs, indent=2, ensure_ascii=False), encoding='utf-8')
        except OSError as exc:
            self.log(f'ERROR saving settings: {exc}', 'error')

    def save_settings(self):
        try:
            self.capture_settings()
        except ValueError as exc:
            messagebox.showerror(self.t('error'), str(exc))
            return
        self.save_settings_file()
        self.status_var.set(self.t('saved'))
        self.log('Settings saved', 'success')

    def reset_settings(self):
        self.prefs = DEFAULTS.copy()
        self.build_ui(self.tabs.index(self.tabs.select()))
        self.save_settings_file()
        self.status_var.set(self.t('reset_done'))
        self.log('Settings reset to defaults')

    def on_auto(self):
        self.prefs['autoscroll'] = self.auto_var.get()
        self.save_settings_file()

    def log(self, message, level='normal'):
        timestamp = datetime.now().strftime('%H:%M:%S') if self.prefs['timestamps'] else ''
        line = f'[{timestamp}] {message}' if timestamp else message
        if level == 'dim' and self.prefs['log_detail'] != 'verbose' and not message.startswith('  '):
            return
        self.console_lines.append(line)
        if len(self.console_lines) > 8000:
            self.console_lines = self.console_lines[-7000:]
        if hasattr(self, 'console_text') and self.console_text.winfo_exists():
            self.console_text.config(state='normal')
            self.console_text.insert('end', line + '\n', level)
            if self.auto_var.get():
                self.console_text.see('end')
            self.console_text.config(state='disabled')

    def render_console(self):
        if not hasattr(self, 'console_text'):
            return
        self.console_text.config(state='normal')
        self.console_text.delete('1.0', 'end')
        self.console_text.insert('end', '\n'.join(self.console_lines) + ('\n' if self.console_lines else ''))
        self.console_text.config(state='disabled')
        if self.auto_var.get():
            self.console_text.see('end')

    def clear_log(self):
        self.console_lines.clear()
        self.render_console()
        self.log('Console cleared')

    def save_log(self):
        path = filedialog.asksaveasfilename(defaultextension='.log',
                 initialfile=f'netscope-{datetime.now():%Y%m%d-%H%M%S}.log',
                 filetypes=[('Log files', '*.log'), ('Text files', '*.txt')])
        if path:
            try:
                Path(path).write_text('\n'.join(self.console_lines) + '\n', encoding='utf-8')
                self.log(f'Log saved: {Path(path).name}', 'success')
            except OSError as exc:
                messagebox.showerror(self.t('error'), str(exc))

    def refresh_interfaces(self):
        if self.scan_active:
            return
        interfaces = get_interfaces()
        labels = [f'{name}   •   {ip}   •   {network}' for name, ip, network in interfaces]
        old_net = self.interface_map.get(self.network_var.get())
        self.interface_map = {label: network for label, (_, _, network) in zip(labels, interfaces)}
        self.network_combo['values'] = labels
        choice = next((label for label in labels if self.interface_map[label] == old_net), None)
        self.network_var.set(choice or (labels[0] if labels else ''))
        self.status_var.set(self.t('ready') if labels else self.t('no_adapter'))
        self.log(f'Network interfaces: {len(labels)} available')
        for label in labels:
            self.log('  ' + label, 'dim')

    def start_scan(self, automated=False):
        if self.scan_active:
            return
        value = self.network_var.get()
        if value not in self.interface_map:
            messagebox.showwarning(self.t('warn_title'), self.t('choose_interface'))
            return
        network = ipaddress.ip_network(self.interface_map[value], strict=False)
        if not allowed_network(network):
            messagebox.showerror(self.t('error'), 'Private RFC1918 networks only.')
            return
        if network.num_addresses > 256:
            messagebox.showwarning(self.t('warn_title'), self.t('too_large'))
            return
        if not automated and self.prefs['confirm'] and not messagebox.askyesno(
               self.t('authorized_title'), self.t('authorize', network=network,
               count=max(network.num_addresses-2, 0))):
            return
        if automated and (not self.monitor_enabled or str(network) != self.monitor_network):
            return
        self.scan_network = str(network)
        self.scan_is_monitor = automated
        self.hosts.clear()
        self.render_hosts()
        self.stop_event.clear()
        self.scan_active = True
        self.started_at = time.monotonic()
        self.count_var.set('0')
        self.checked_var.set('0 / 0')
        self.elapsed_var.set('0.0s')
        self.progress['value'] = 0
        self.apply_busy_state()
        self.status_var.set(self.t('scan_running', network=network))
        prefs = self.prefs.copy()
        self.log(f'SCAN START {network} • threads={prefs["workers"]} • timeout={prefs["timeout"]}ms')
        threading.Thread(target=self.scan_worker, args=(network, prefs), daemon=True).start()

    def scan_worker(self, network: ipaddress.IPv4Network, prefs: dict):
        ips = [str(ip) for ip in network.hosts()]
        total = len(ips)
        self.events.put(('total', total))
        finished = 0
        with ThreadPoolExecutor(max_workers=prefs['workers']) as pool:
            tasks = {pool.submit(ping_host, ip, prefs['timeout']): ip for ip in ips}
            for future in as_completed(tasks):
                ip = tasks[future]
                if self.stop_event.is_set():
                    for pending in tasks:
                        pending.cancel()
                    break
                try:
                    latency = future.result()
                except Exception as exc:
                    self.events.put(('log', f'ERROR ping {ip}: {exc}', 'error'))
                    latency = None
                if latency is not None:
                    self.events.put(('host', Host(ip=ip, latency_ms=latency)))
                    self.events.put(('log', f'REPLY {ip:<15}  {latency:.1f} ms', 'success'))
                elif prefs['show_misses']:
                    self.events.put(('log', f'TIMEOUT {ip}', 'dim'))
                finished += 1
                self.events.put(('progress', finished, total))
        if not self.stop_event.is_set() and prefs['arp']:
            arp = read_arp_table()
            for ip, mac in arp.items():
                try:
                    if ipaddress.ip_address(ip) in network and ipaddress.ip_address(ip) != network.network_address and ipaddress.ip_address(ip) != network.broadcast_address:
                        self.events.put(('arp', ip, mac))
                        self.events.put(('log', f'ARP {ip:<15}  {mac}', 'success'))
                except ValueError:
                    continue
        self.events.put(('done', self.stop_event.is_set(), finished, total))
        if not self.stop_event.is_set() and prefs['dns']:
            for ip in list(self._dns_target_ips):
                if self.stop_event.is_set():
                    break
                name = reverse_hostname(ip)
                if name != '—':
                    self.events.put(('hostname', ip, name))
                    self.events.put(('log', f'DNS {ip} → {name}', 'success'))

    @property
    def _dns_target_ips(self):
        # Read-only snapshot from worker; GIL makes list copy safe for this use.
        return list(self.hosts)

    def stop_scan(self):
        self.stop_event.set()
        self.status_var.set(self.t('stopping'))
        self.log('STOP requested')
        self.apply_busy_state()

    def scan_selected_ports(self):
        self.run_diagnostic(kind='ports', common=True)

    def on_select(self, _event=None):
        selection = self.tree.selection()
        if selection:
            self.last_selected_ip = selection[0]
            if hasattr(self, 'target_var'):
                self.target_var.set(self.last_selected_ip)

    def selected_ip(self):
        selection = self.tree.selection()
        return selection[0] if selection else self.last_selected_ip

    def run_diagnostic(self, kind=None, common=False):
        if self.diagnostic_active:
            messagebox.showinfo(self.t('warn_title'), self.t('test_busy'))
            return
        kind = kind or self.tool_labels.get(self.tool_var.get(), 'ping')
        ip = (self.target_var.get().strip() if hasattr(self, 'target_var') else '') or self.selected_ip() or ''
        if needs_target(kind):
            try:
                target = ipaddress.IPv4Address(ip)
                if not any(target in block for block in (
                        ipaddress.ip_network('10.0.0.0/8'),
                        ipaddress.ip_network('172.16.0.0/12'),
                        ipaddress.ip_network('192.168.0.0/16'))):
                    raise ValueError()
            except ValueError:
                messagebox.showerror(self.t('error'), self.tool_text('private_target'))
                return
            ip = str(target)
        ports = COMMON_PORTS
        if kind == 'ports' and not common:
            try:
                values = [int(x.strip()) for x in self.custom_ports_var.get().split(',') if x.strip()]
                if not values or len(values) > 32 or any(not 1 <= n <= 65535 for n in values):
                    raise ValueError()
                ports = {n: COMMON_PORTS.get(n, 'TCP') for n in dict.fromkeys(values)}
            except ValueError:
                messagebox.showerror(self.t('error'), 'Enter 1–32 valid TCP ports (1–65535).')
                return
        if kind == 'ports' and not messagebox.askyesno(self.t('authorized_title'),
                      self.t('ports_confirm', count=len(ports), ip=ip)):
            return
        if needs_target(kind) and self.prefs['confirm'] and kind != 'ports':
            if not messagebox.askyesno(self.t('authorized_title'),
                    self.tool_text('permission') + f'\n{ip}'):
                return
        self.diagnostic_active = True
        self.apply_busy_state()
        self.tabs.select(self.console_tab)
        self.log(f'TEST START {kind.upper()} → {ip or "LOCAL"}')
        threading.Thread(target=self.diagnostic_worker, args=(kind, ip, ports), daemon=True).start()

    def diagnostic_worker(self, kind, ip, ports):
        def emit(line, level='normal'):
            self.events.put(('log', str(line), level))
        try:
            if kind == 'ports':
                opened = []
                for port, service in ports.items():
                    try:
                        with socket.create_connection((ip, port), timeout=0.35):
                            opened.append(f'{port} ({service})')
                            emit(f'OPEN  {ip}:{port} {service}', 'success')
                    except OSError:
                        emit(f'CLOSED/FILTERED {ip}:{port}', 'dim')
                result = ', '.join(opened) if opened else 'None detected'
                self.events.put(('ports', ip, result))
            elif kind == 'dns':
                name = reverse_hostname(ip)
                emit(f'Reverse DNS {ip}: {name}', 'success' if name != '—' else 'normal')
                if name != '—':
                    self.events.put(('hostname', ip, name))
            elif kind in ('ping', 'trace'):
                cmd = (["ping", "-n", "4", "-w", "800", ip] if os.name == 'nt' else
                       ["ping", "-c", "4", "-W", "1", ip]) if kind == 'ping' else (
                       ["tracert", "-d", "-w", "600", "-h", "12", ip] if os.name == 'nt' else
                       ["traceroute", "-n", "-w", "1", "-m", "12", ip])
                proc = subprocess.run(cmd, capture_output=True, text=True, errors='replace',
                      timeout=55, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                for line in (proc.stdout + '\n' + proc.stderr).splitlines():
                    if line.strip():
                        emit('  ' + line.strip())
                emit(f'{kind.upper()} exit code: {proc.returncode}')
            else:
                run_extra_tool(kind, ip, emit)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            emit(f'ERROR {kind}: {exc}', 'error')
        finally:
            self.events.put(('diagnostic_done', kind, ip or 'LOCAL'))

    def process_events(self):
        try:
            for _ in range(250):
                event = self.events.get_nowait()
                kind = event[0]
                if kind == 'total':
                    self.checked_var.set(f'0 / {event[1]}')
                elif kind == 'host':
                    host = event[1]
                    old = self.hosts.get(host.ip)
                    if old:
                        old.latency_ms = host.latency_ms
                    else:
                        self.hosts[host.ip] = host
                    self.count_var.set(str(len(self.hosts)))
                    self.update_row(host.ip)
                elif kind == 'arp':
                    ip, mac = event[1:]
                    if ip not in self.hosts:
                        self.hosts[ip] = Host(ip=ip, mac=mac)
                    else:
                        self.hosts[ip].mac = mac
                    self.count_var.set(str(len(self.hosts)))
                    self.update_row(ip)
                elif kind == 'hostname':
                    ip, name = event[1:]
                    if ip in self.hosts:
                        self.hosts[ip].hostname = name
                        self.update_row(ip)
                elif kind == 'progress':
                    checked, total = event[1:]
                    self.checked_var.set(f'{checked} / {total}')
                    self.progress['value'] = (100 * checked / total) if total else 100
                    if self.started_at:
                        self.elapsed_var.set(f'{time.monotonic()-self.started_at:.1f}s')
                elif kind == 'done':
                    stopped, finished, total = event[1:]
                    self.scan_active = False
                    self.apply_busy_state()
                    elapsed = time.monotonic()-self.started_at if self.started_at else 0
                    self.elapsed_var.set(f'{elapsed:.1f}s')
                    self.status_var.set(self.t('stopped' if stopped else 'finished', count=len(self.hosts)))
                    self.log(f'SCAN {"STOPPED" if stopped else "COMPLETE"} • {finished}/{total} checked • {len(self.hosts)} hosts • {elapsed:.1f}s', 'success')
                    self.on_scan_snapshot(stopped, elapsed)
                elif kind == 'ports':
                    ip, value = event[1:]
                    if ip in self.hosts:
                        self.hosts[ip].open_ports = value
                        self.update_row(ip)
                elif kind == 'diagnostic_done':
                    self.diagnostic_active = False
                    self.apply_busy_state()
                    self.log(f'TEST COMPLETE {event[1].upper()} → {event[2]}', 'success')
                elif kind == 'log':
                    self.log(event[1], event[2])
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(70, self.process_events)

    def update_row(self, ip):
        if not hasattr(self, 'tree') or not self.tree.winfo_exists():
            return
        host = self.hosts[ip]
        q = self.filter_var.get().strip().lower()
        if q and q not in f'{host.ip} {host.hostname} {host.mac} {host.open_ports}'.lower():
            if self.tree.exists(ip):
                self.tree.delete(ip)
            return
        ping = f'{host.latency_ms:.0f} ms' if host.latency_ms is not None else self.t('no_icmp')
        ports = host.open_ports
        if ports == 'Not checked':
            ports = self.t('not_checked')
        elif ports == 'None detected':
            ports = self.t('none_found')
        values = (host.ip, host.hostname, host.mac, ping, ports)
        if self.tree.exists(ip):
            self.tree.item(ip, values=values)
        else:
            self.tree.insert('', 'end', iid=ip, values=values,
                             tags=('odd' if len(self.tree.get_children()) % 2 else 'even',))

    def render_hosts(self):
        if not hasattr(self, 'tree') or not self.tree.winfo_exists():
            return
        selected = self.last_selected_ip
        self.tree.delete(*self.tree.get_children())
        for ip in sorted(self.hosts, key=ipaddress.ip_address):
            self.update_row(ip)
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)

    def sort_by(self, col):
        items = list(self.tree.get_children())
        idx = {'ip':0,'hostname':1,'mac':2,'latency':3,'ports':4}[col]
        reverse = getattr(self, '_sort_col', None) == col and not getattr(self, '_sort_rev', False)
        self._sort_col, self._sort_rev = col, reverse
        def key(item):
            host = self.hosts[item]
            if col == 'ip':
                return int(ipaddress.ip_address(item))
            if col == 'latency':
                return host.latency_ms if host.latency_ms is not None else 1e9
            return str(self.tree.item(item, 'values')[idx]).lower()
        for position, item in enumerate(sorted(items, key=key, reverse=reverse)):
            self.tree.move(item, '', position)

    def context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.on_select()
        menu = tk.Menu(self.root, tearoff=0, bg=PANEL2, fg=TEXT,
                       activebackground=ACCENT, activeforeground=BG)
        menu.add_command(label=self.t('copy_ip'), command=lambda: self.copy_value(iid))
        menu.add_command(label=self.t('copy_mac'), command=lambda: self.copy_value(self.hosts[iid].mac))
        menu.add_command(label=self.t('ports'), command=self.scan_selected_ports)
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def copy_value(self, value):
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.log(f'Copied to clipboard: {value}')

    def export(self):
        if not self.hosts:
            messagebox.showinfo(self.t('warn_title'), self.t('no_results'))
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv',
               initialfile=f'netscope-{datetime.now():%Y%m%d-%H%M%S}.csv',
               filetypes=[('CSV', '*.csv'), ('JSON', '*.json')])
        if not path:
            return
        rows = [asdict(self.hosts[ip]) for ip in sorted(self.hosts, key=ipaddress.ip_address)]
        try:
            if Path(path).suffix.lower() == '.json':
                with open(path, 'w', encoding='utf-8') as file:
                    json.dump({'app':APP_TITLE, 'version':VERSION,
                               'exported_at':datetime.now().astimezone().isoformat(),
                               'devices':rows}, file, ensure_ascii=False, indent=2)
            else:
                with open(path, 'w', encoding='utf-8-sig', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=list(Host.__dataclass_fields__))
                    writer.writeheader()
                    writer.writerows(rows)
            self.status_var.set(self.t('exported', count=len(rows), name=Path(path).name))
            self.log(f'EXPORT {len(rows)} devices → {path}', 'success')
        except OSError as exc:
            messagebox.showerror(self.t('error'), str(exc))
            self.log(f'ERROR export: {exc}', 'error')

    def on_close(self):
        self.stop_event.set()
        self.monitor_enabled = False
        self.root.destroy()


def main():
    root = tk.Tk()
    root.withdraw()
    if not first_launch_language(root):
        root.destroy()
        return
    NetScopeApp(root)
    root.deiconify()
    root.mainloop()

if __name__ == '__main__':
    main()
