# 🌐 NetScope 4.0 — Découverte, diagnostic et surveillance réseau

## 🌍 Documentation — Choisissez votre langue

**🇫🇷 Français (par défaut)** · 🇬🇧 English · 🇩🇪 Deutsch · 🇪🇸 Español · 🇮🇹 Italiano · 🇯🇵 日本語 · 🇰🇷 한국어 · 🇵🇹 Português · 🇷🇺 Русский · 🇨🇳 简体中文

La documentation complète en **français est affichée ci-dessous**. La version anglaise et les huit autres traductions sont accessibles dans des sections déroulantes. Dans l'application, la langue est proposée au premier lancement et peut être modifiée dans **Settings**.

---

## Présentation

**NetScope** est un logiciel Windows open source conçu pour **les réseaux locaux privés que vous possédez ou êtes autorisé à administrer**. Il propose une interface sombre, une console de diagnostic intégrée, une icône Windows personnalisée, **22 outils de diagnostic**, un tableau de bord de surveillance et un historique local.

## Nouveautés de la version 4.0

- **Surveillance :** analyses périodiques facultatives du réseau local (toutes les 30 à 3 600 secondes). Une première analyse sert de référence ; les suivantes signalent les adresses nouvellement détectées ou qui ne répondent plus. Vous pouvez démarrer, arrêter et consulter le compte à rebours. Le sous-réseau choisi doit rester identique pendant la surveillance.
- **Alertes :** notifications intégrées facultatives, signal sonore et messages dans la console. Une alerte ne prouve pas qu'un appareil vient de se connecter ou de se déconnecter : pare-feu, veille Wi-Fi, absence de réponse ICMP ou variations du cache ARP peuvent provoquer des différences.
- **Tableau de bord :** débits de téléchargement et d'envoi mis à jour chaque seconde, graphique du trafic total du PC et graphique de latence moyenne par analyse achevée (pas une mesure continue de chaque appareil).
- **Connexions actives :** affichage périodique des connexions établies **par votre PC**, regroupées par IP distante. Ce n'est ni un outil de capture de paquets ni un moyen de consulter les connexions des autres appareils. Certaines informations exigent des autorisations système.
- **Historique :** base SQLite locale enregistrant les analyses et les changements, avec date, sous-réseau, nombre d'appareils et durée. Possibilité de rafraîchir, exporter les événements en CSV ou supprimer l'historique.
- **Paramètres :** intervalle de surveillance enregistré, notifications activables et autres options déjà présentes.
- **Internationalisation :** interface de surveillance et historique traduits dans les dix langues prises en charge, avec choix de la langue au premier démarrage.

## Fonctionnalités de diagnostic

**22 outils :** ping (4 essais), DNS inversé, traceroute, analyse de ports TCP (32 ports maximum), temps de connexion TCP, en-têtes HTTP, inspection TLS (protocole, chiffrement, empreinte), informations IP, calculateur de sous-réseau /24 à titre d'exemple, série de 10 pings, informations système, cartes réseau, configuration IP, cache ARP/voisins, table de routage, connexions TCP/UDP, mesure de débit, configuration DNS, informations Wi-Fi, test de passerelle, test de boucle locale et bilan de santé réseau.

NetScope propose aussi la découverte d'adresses IPv4 privées (254 hôtes maximum par analyse), une estimation de la latence, l'enrichissement ARP, la résolution facultative des noms d'hôtes, la recherche et le tri, l'export CSV/JSON, une console de diagnostic et l'enregistrement des logs. Certaines commandes dépendent de Windows.

## Compiler `NetScope.exe` sur Windows

1. Installez **Python 3.11 ou une version plus récente** depuis python.org.
2. Décompressez l'archive du projet.
3. Double-cliquez sur **`build.bat`** : il installe les dépendances et lance PyInstaller.
4. Retrouvez **`dist\NetScope.exe`**. L'icône `assets/netscope.ico` est intégrée à l'exécutable.

Autre possibilité : publiez le projet sur GitHub, ouvrez **Actions → Build NetScope for Windows**, puis téléchargez l'artefact `NetScope-Windows-x64`. **Le ZIP du code source ne contient pas de fichier `.exe` précompilé.**

Pour lancer le logiciel depuis les sources :

```powershell
py -m pip install psutil
py netscope.py
```

Pour lancer les tests automatisés hors ligne :

```powershell
py -m unittest discover -s tests -v
```

## Utiliser la surveillance

1. Dans l'onglet **Devices**, sélectionnez une interface privée appartenant à un réseau que vous administrez.
2. Ouvrez **Monitor** et choisissez l'intervalle (60 secondes par défaut, 30 secondes minimum).
3. Cliquez sur **Start monitoring**, puis confirmez explicitement que vous êtes autorisé à effectuer des scans répétés.
4. Attendez la fin de l'analyse de référence. Les analyses suivantes enregistrent les changements d'IP détectées. Le graphique de trafic peut fonctionner même lorsque la surveillance automatique est arrêtée.
5. Consultez **History** pour les événements et les bilans. Vous pouvez désactiver les notifications dans **Settings**, ou arrêter la surveillance à tout moment.

Les scans sont limités aux sous-réseaux IPv4 privés RFC1918 de 256 adresses au maximum (/24 ou plus petits). NetScope **n'intercepte pas le trafic réseau**, ne garantit pas de découvrir tous les appareils et ne peut pas certifier qu'un appareil absent est déconnecté.

## Confidentialité et stockage

Aucun compte, service cloud ou système de télémétrie. Les réglages se trouvent dans `%APPDATA%\NetScope\settings.json` et l'historique dans `%APPDATA%\NetScope\history.sqlite3`. Les exports de résultats et les logs sont enregistrés uniquement à la demande. Ils peuvent contenir des adresses IP ou MAC sensibles : vérifiez-les avant de les partager.

N'effectuez des analyses que sur les réseaux pour lesquels vous disposez d'une autorisation. La surveillance ne démarre jamais automatiquement avec NetScope : elle exige une action et une confirmation à chaque session.

## Fichiers du projet

```text
netscope.py                 Interface, découverte et diagnostics
monitoring.py               Surveillance, historique SQLite, graphiques et alertes
translations.py             Textes de l'interface dans 10 langues
diagnostics_extra.py        Outils de diagnostic complémentaires
assets/netscope.ico         Icône de l'exécutable Windows
assets/netscope.png         Icône de la fenêtre
build.bat                   Compilation de l'exécutable Windows
.github/workflows/         Compilation Windows via GitHub Actions
tests/test_monitoring.py    Tests automatisés hors ligne
```

## Tests et limites

La syntaxe Python, les tests hors ligne de la base SQLite et de l'historique ainsi qu'un test graphique sans écran ont été validés sous Linux. **L'exécutable Windows, les commandes propres à Windows et la surveillance sur un véritable réseau Windows n'ont pas encore été testés** dans cet environnement. Certaines informations et commandes nécessitent des droits supplémentaires.

Licence **MIT** : consultez le fichier `LICENSE`.

---

<details>
<summary><strong>🇬🇧 English — Click to expand</strong></summary>

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

</details>

<details>
<summary><strong>🇩🇪 Deutsch</strong></summary>

### Überblick
**NetScope** ist ein quelloffenes Windows-Tool zur Erkennung, Diagnose und Überwachung von Geräten in einem privaten Netzwerk, für das Sie eine Berechtigung haben. Es bietet eine dunkle Oberfläche, eine Diagnosekonsole, 22 Werkzeuge, Verkehrsdiagramme, Warnungen und einen lokalen Verlauf.

### Funktionen
- Geräteerkennung mit verfügbaren IP-/MAC-Adressen, DNS-Auflösung sowie CSV-/JSON-Export.
- Ping, Traceroute, TCP-Portprüfung, Latenz, HTTP, TLS und System-/Netzwerkdiagnosen.
- Optionale regelmäßige Scans, Änderungswarnungen und Echtzeitdiagramme.
- Lokaler SQLite-Verlauf und anpassbare Einstellungen.
- Sprachauswahl beim ersten Start; später unter **Settings** änderbar.

### Windows-Build
Installieren Sie **Python 3.11+**, entpacken Sie das Archiv und starten Sie `build.bat`. Die Datei liegt danach unter `dist\NetScope.exe`. Alternativ können Sie das Windows-Artefakt aus **GitHub Actions** herunterladen. Das Quellarchiv enthält keine vorkompilierte EXE.

### Datenschutz und Grenzen
Keine Konten, Cloud-Dienste oder Telemetrie. Einstellungen und Verlauf bleiben lokal. Scannen Sie nur Netzwerke, für die Sie eine Erlaubnis haben. Nicht erkannte Geräte sind nicht zwangsläufig offline. Der Windows-Build und Windows-spezifische Diagnosen wurden noch nicht in einem echten Windows-Netzwerk getestet.

</details>

<details>
<summary><strong>🇪🇸 Español</strong></summary>

### Descripción
**NetScope** es una herramienta de código abierto para Windows que permite descubrir, diagnosticar y supervisar dispositivos en redes privadas autorizadas. Incluye una interfaz oscura, consola de diagnóstico, 22 herramientas, gráficos de tráfico, alertas e historial local.

### Funciones
- Descubrimiento de dispositivos, direcciones IP/MAC disponibles, DNS y exportación CSV/JSON.
- Ping, traceroute, puertos TCP, latencia, HTTP, TLS y diagnósticos del sistema y la red.
- Escaneos periódicos opcionales, alertas de cambios y gráficos en tiempo real.
- Historial SQLite local y ajustes personalizables.
- Selección de idioma en el primer inicio; también desde **Settings**.

### Compilación en Windows
Instala **Python 3.11+**, extrae el archivo y ejecuta `build.bat`. Encontrarás el ejecutable en `dist\NetScope.exe`. También puedes obtenerlo desde **GitHub Actions** después de compilarlo. El ZIP del código fuente no incluye un `.exe` compilado.

### Privacidad y limitaciones
Sin cuentas, nube ni telemetría. Los ajustes y el historial se guardan localmente. Analiza solo redes para las que tengas permiso. Un dispositivo no detectado no siempre está desconectado. El ejecutable y los diagnósticos específicos de Windows aún no se han probado en una red Windows real.

</details>

<details>
<summary><strong>🇮🇹 Italiano</strong></summary>

### Panoramica
**NetScope** è uno strumento open source per Windows che consente di rilevare, diagnosticare e monitorare dispositivi su reti private autorizzate. Include un'interfaccia scura, console diagnostica, 22 strumenti, grafici del traffico, avvisi e cronologia locale.

### Funzionalità
- Rilevamento dei dispositivi, indirizzi IP/MAC disponibili, DNS ed esportazione CSV/JSON.
- Ping, traceroute, porte TCP, latenza, HTTP, TLS e diagnostica del sistema e della rete.
- Scansioni periodiche facoltative, avvisi sui cambiamenti e grafici in tempo reale.
- Cronologia SQLite locale e impostazioni personalizzabili.
- Scelta della lingua al primo avvio, modificabile in **Settings**.

### Compilazione su Windows
Installa **Python 3.11+**, estrai l'archivio ed esegui `build.bat`. Troverai il programma in `dist\NetScope.exe`. In alternativa scarica l'artefatto da **GitHub Actions** dopo la compilazione. L'archivio sorgente non contiene un `.exe` già compilato.

### Privacy e limiti
Nessun account, cloud o telemetria. Impostazioni e cronologia restano sul PC. Esegui scansioni solo sulle reti per cui hai l'autorizzazione. Un dispositivo non rilevato non è necessariamente offline. Il file EXE e le diagnosi specifiche di Windows non sono ancora stati testati su una rete Windows reale.

</details>

<details>
<summary><strong>🇯🇵 日本語</strong></summary>

### 概要
**NetScope** は、管理権限のあるプライベートネットワーク上の機器を検出・診断・監視する、Windows 向けのオープンソースツールです。ダークテーマの画面、診断コンソール、22 種類のツール、通信量グラフ、通知、ローカル履歴を備えています。

### 主な機能
- デバイス検出、取得可能な IP/MAC アドレス、DNS 解決、CSV/JSON 出力。
- Ping、traceroute、TCP ポート検査、遅延、HTTP、TLS、システム・ネットワーク診断。
- 任意で有効にする定期スキャン、変化の通知、リアルタイムグラフ。
- ローカル SQLite 履歴とカスタマイズ可能な設定。
- 初回起動時の言語選択。後から **Settings** でも変更可能。

### Windows でのビルド
**Python 3.11 以降**をインストールし、ZIP を展開して `build.bat` を実行してください。`dist\NetScope.exe` が生成されます。ビルド後に **GitHub Actions** の成果物から取得することもできます。ソース ZIP にコンパイル済み EXE は含まれません。

### プライバシーと注意事項
アカウント、クラウド、利用状況の送信はありません。設定と履歴は PC 内に保存されます。許可されたネットワークでのみ使用してください。検出されない機器が必ずしもオフラインとは限りません。Windows 向け EXE と Windows 固有の診断は、実際の Windows ネットワークで未検証です。

</details>

<details>
<summary><strong>🇰🇷 한국어</strong></summary>

### 소개
**NetScope**는 관리 권한이 있는 사설 네트워크의 장치를 검색, 진단, 모니터링하는 Windows용 오픈 소스 도구입니다. 다크 UI, 진단 콘솔, 22가지 도구, 트래픽 그래프, 알림 및 로컬 기록을 제공합니다.

### 주요 기능
- 장치 검색, 확인 가능한 IP/MAC 주소, DNS 조회, CSV/JSON 내보내기.
- Ping, traceroute, TCP 포트, 지연 시간, HTTP, TLS 및 시스템/네트워크 진단.
- 선택적으로 실행하는 정기 스캔, 변경 알림, 실시간 그래프.
- 로컬 SQLite 기록과 사용자 지정 설정.
- 첫 실행 시 언어 선택, 이후 **Settings**에서 변경 가능.

### Windows 빌드
**Python 3.11 이상**을 설치하고 압축을 푼 뒤 `build.bat`를 실행하세요. `dist\NetScope.exe`가 생성됩니다. 빌드 후 **GitHub Actions** 아티팩트에서도 받을 수 있습니다. 소스 ZIP에는 미리 빌드된 EXE가 없습니다.

### 개인정보 보호 및 제한 사항
계정, 클라우드 서비스, 원격 텔레메트리가 없습니다. 설정과 기록은 PC에 저장됩니다. 허가받은 네트워크에서만 스캔하세요. 검색되지 않은 장치가 반드시 오프라인인 것은 아닙니다. Windows 실행 파일과 Windows 전용 진단은 실제 Windows 네트워크에서 아직 검증되지 않았습니다.

</details>

<details>
<summary><strong>🇵🇹 Português</strong></summary>

### Visão geral
**NetScope** é uma ferramenta Windows de código aberto para descobrir, diagnosticar e monitorizar dispositivos em redes privadas autorizadas. Inclui uma interface escura, consola de diagnóstico, 22 ferramentas, gráficos de tráfego, alertas e histórico local.

### Funcionalidades
- Descoberta de dispositivos, endereços IP/MAC disponíveis, DNS e exportação CSV/JSON.
- Ping, traceroute, portas TCP, latência, HTTP, TLS e diagnósticos do sistema e da rede.
- Análises periódicas opcionais, alertas de alterações e gráficos em tempo real.
- Histórico SQLite local e definições personalizáveis.
- Seleção de idioma no primeiro arranque e alteração posterior em **Settings**.

### Compilação no Windows
Instala **Python 3.11+**, extrai o arquivo e executa `build.bat`. O programa fica em `dist\NetScope.exe`. Também podes descarregar o artefacto de **GitHub Actions** após a compilação. O ZIP com o código-fonte não inclui um EXE pré-compilado.

### Privacidade e limitações
Sem contas, nuvem ou telemetria. As definições e o histórico são guardados localmente. Analisa apenas redes para as quais tens autorização. Um dispositivo não detetado não está necessariamente offline. O EXE e os diagnósticos específicos do Windows ainda não foram testados numa rede Windows real.

</details>

<details>
<summary><strong>🇷🇺 Русский</strong></summary>

### Обзор
**NetScope** — инструмент с открытым исходным кодом для Windows, предназначенный для обнаружения, диагностики и мониторинга устройств в частных сетях, к которым у вас есть разрешённый доступ. Включает тёмный интерфейс, консоль диагностики, 22 инструмента, графики трафика, уведомления и локальную историю.

### Возможности
- Поиск устройств, доступные IP/MAC-адреса, DNS и экспорт CSV/JSON.
- Ping, traceroute, проверка TCP-портов, задержки, HTTP, TLS и диагностика системы/сети.
- Необязательные периодические проверки, уведомления об изменениях и графики в реальном времени.
- Локальная история SQLite и настраиваемые параметры.
- Выбор языка при первом запуске; позже его можно изменить в **Settings**.

### Сборка для Windows
Установите **Python 3.11+**, распакуйте архив и запустите `build.bat`. Файл появится по пути `dist\NetScope.exe`. После сборки его также можно скачать из **GitHub Actions**. Архив исходников не содержит готового EXE.

### Конфиденциальность и ограничения
Учётная запись, облако и телеметрия не требуются. Настройки и история сохраняются локально. Сканируйте только сети, на проверку которых у вас есть разрешение. Отсутствие ответа не обязательно означает отключение устройства. EXE и функции диагностики Windows ещё не проверялись в реальной сети Windows.

</details>

<details>
<summary><strong>🇨🇳 简体中文</strong></summary>

### 简介
**NetScope** 是一款面向 Windows 的开源工具，可用于发现、诊断和监控您有权管理的私有网络中的设备。提供深色界面、诊断控制台、22 种工具、流量图表、提醒和本地历史记录。

### 主要功能
- 设备发现、可获取的 IP/MAC 地址、DNS 查询，以及 CSV/JSON 导出。
- Ping、路由跟踪、TCP 端口检测、延迟、HTTP、TLS 和系统/网络诊断。
- 可选的定期扫描、设备变化提醒和实时图表。
- 本地 SQLite 历史记录与可自定义设置。
- 首次启动时选择语言，也可在 **Settings** 中修改。

### 在 Windows 上构建
安装 **Python 3.11 或更高版本**，解压项目并运行 `build.bat`，生成的文件位于 `dist\NetScope.exe`。构建后也可从 **GitHub Actions** 下载。源代码 ZIP 不包含预编译的 EXE。

### 隐私与限制
无需账户、云服务或遥测。设置与历史记录保存在本机。请仅扫描获得授权的网络。未检测到设备不一定表示设备已离线。Windows EXE 和 Windows 专用诊断尚未在真实 Windows 网络中验证。

</details>
