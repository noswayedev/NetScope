# NetScope 4.0 — Network Discovery, Diagnostics & Monitoring

**NetScope** is a Windows-first, privacy-friendly network toolkit designed for **your own or authorized private LAN**. It includes a dark desktop interface, a built-in diagnostic console, a custom Windows icon, **22 diagnostic tools**, and an all-new local monitoring dashboard.

## New in 4.0

- **Monitor:** opt-in periodic LAN scans (every 30–3600 seconds). An initial baseline is saved, then later scans identify **newly detected** and **no longer detected** addresses. Start/stop buttons and a countdown are provided. The selected LAN must remain unchanged while monitoring.
- **In-app alerts:** optional non-blocking alert popups and an audible notification for changes; alert logging in the live console. Alerts do **not** imply definite device joins/disconnects: ICMP failures, Wi-Fi sleep, firewall rules and ARP cache fluctuations can produce false changes.
- **Live dashboard:** per-second download/upload rates and an animated traffic chart, based on this PC's total network I/O counters. A second chart shows average ping latency across detected devices **per completed scan** (not continuous latency sampling).
- **Connections view:** a periodically refreshed list of established **local PC** connections, grouped by remote IP, using system socket metadata. This is **not a packet sniffer** or a map of other devices' connections; complete access depends on operating-system permissions.
- **History:** locally persisted SQLite snapshots and change events with date, subnet, device count and scan duration. Export change events to CSV, refresh or delete local history.
- **Settings:** retain all original settings, plus the toggle for in-app device-change alerts. The chosen monitoring interval is saved.
- **International:** the new monitoring and history UI is translated into all ten supported languages: Français, English, Deutsch, Español, Italiano, 日本語, 한국어, Português, Русский, 简体中文. The first-launch language selector remains available.

## Features kept from v3

**22 diagnostic tools:** Ping ×4, reverse DNS, traceroute, TCP port scan (up to 32 ports), TCP connection timing, HTTP headers, TLS inspection (protocol/cipher/fingerprint), IP details, example /24 subnet calculator, ten-sample ping series; system overview, network adapters, IP configuration, ARP/neighbor cache, routing table, TCP/UDP socket list, throughput snapshot, DNS settings, Wi-Fi details, gateway test, loopback and network health summary.

Also includes private IPv4 discovery (max 254 hosts / scan), approximate ping timing, ARP enrichment, optional hostnames, sortable/filterable results, JSON/CSV device export, diagnostic console and file logging. Some built-in command diagnostics are Windows-specific.

## Build `NetScope.exe` on Windows

1. Install **Python 3.11+** from python.org.
2. Extract the project archive.
3. Double-click **`build.bat`**. This installs dependencies and builds with PyInstaller.
4. Find **`dist\NetScope.exe`**. `assets/netscope.ico` is embedded in the Windows executable.

Alternatively publish to GitHub and use **Actions → Build NetScope for Windows**; download the `NetScope-Windows-x64` artifact. **The source ZIP does not contain a precompiled executable.**

Run from source:

```powershell
py -m pip install psutil
py netscope.py
```

Tests (no live network required):

```powershell
py -m unittest discover -s tests -v
```

## How to use monitoring

1. In **Devices**, choose the private interface that belongs to a network you administer.
2. Open **Monitor** and choose a scan interval (60 seconds by default; minimum 30).
3. Click **Start monitoring** and explicitly confirm your authorization to send repeated scans to the chosen subnet.
4. Allow the baseline scan to finish, then subsequent completed scans generate events when the set of detected IPs changes. The network traffic graph runs even when automated scans are off.
5. Open **History** for saved events and scan summaries; use **Settings** to disable pop-up alerts. Stop monitoring at any time.

Scans are restricted to RFC1918 private IPv4 subnets containing no more than 256 total addresses (/24 or smaller). The app does not monitor or intercept packets. It **does not guarantee detection of all network devices** or verify whether missing hosts really went offline.

## Data storage and privacy

No account, cloud service or telemetry. Settings: `%APPDATA%\NetScope\settings.json`. History: `%APPDATA%\NetScope\history.sqlite3`. Event exports and device lists are saved only on explicit user request. Logs/history may contain sensitive IP/MAC addresses—review before sharing.

Only run scans and diagnostics on networks where you have permission. Monitoring does not auto-start when you launch NetScope: it requires an explicit user action and consent each session.

## Project files

```text
netscope.py                 Desktop interface, discovery, diagnostics
monitoring.py               Monitoring UI, SQLite history, charts and notifications
translations.py             UI text for ten languages
diagnostics_extra.py        Additional diagnostic tools
assets/netscope.ico         Windows executable icon
assets/netscope.png         Window icon
build.bat                   Build standalone Windows executable
.github/workflows/         Windows GitHub Actions build
tests/test_monitoring.py    Offline automated tests
```

## Testing and limitations

Python syntax, offline SQLite/history tests and a headless graphical interface smoke test have passed on Linux. The Windows `.exe`, Windows-specific commands and monitoring against a real network **have not yet been tested** in this environment. Some OS commands and socket details require additional privileges.

Licensed under the MIT license (see `LICENSE`).
