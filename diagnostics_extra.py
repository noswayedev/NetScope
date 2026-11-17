"""Bounded, local-first network diagnostics for authorized networks."""
from __future__ import annotations
import ipaddress
import os
import platform
import socket
import ssl
import subprocess
import time
from datetime import datetime
import psutil

TOOL_DEFS = [
    ('ping', 'remote'), ('dns','remote'), ('trace','remote'), ('ports','remote'),
    ('tcp_latency','remote'), ('http_headers','remote'), ('tls','remote'),
    ('host_detail','remote'), ('subnet','remote'), ('ping_series','remote'),
    ('system','local'), ('interfaces','local'), ('ip_config','local'),
    ('arp_table','local'), ('route_table','local'), ('connections','local'),
    ('traffic','local'), ('dns_servers','local'), ('wifi','local'),
    ('gateway','local'), ('loopback','local'), ('net_health','local'),
]
LOCAL_TOOLS = {'system','interfaces','ip_config','arp_table','route_table',
               'connections','traffic','dns_servers','wifi','gateway',
               'loopback','net_health'}
def needs_target(kind):
    return kind not in LOCAL_TOOLS

# Tool names are translated in all ten supported UI languages.
TOOL_TRANSLATIONS = {
'en': dict(remote='DEVICE TESTS',local='THIS COMPUTER',intro='22 diagnostics • Select a tool and run it. Tests stream to Live Console. Remote tests are restricted to private IPv4 addresses.', target='Target IPv4 (from discovery or enter a private IP)',select='DIAGNOSTIC TOOL',port_hint='Custom TCP ports (used by TCP port scan, max 32)',note_title='SAFETY & LIMITS',note='Run only on your own or authorized network. A blocked ICMP reply does not prove a host is offline. No packet capture, exploitation, credential extraction or external telemetry.',private_target='Enter a valid private IPv4 address (10.x, 172.16–31.x, or 192.168.x).',permission='Do you have authorization to test this device?',ping='Ping ×4',dns='Reverse DNS',trace='Traceroute',ports='TCP port scan',tcp_latency='TCP connect timing',http_headers='HTTP response headers',tls='TLS certificate (443)',host_detail='IP & local neighbor data',subnet='Subnet calculations (/24)',ping_series='Latency series (10 samples)',system='System overview',interfaces='Network adapters',ip_config='IP configuration',arp_table='ARP / neighbor cache',route_table='Routing table',connections='TCP/UDP connections',traffic='Network traffic snapshot',dns_servers='DNS resolver settings',wifi='Wi-Fi connection details',gateway='Default gateway',loopback='Local loopback test',net_health='Local health report'),
'fr': dict(remote='TESTS APPAREILS',local='CET ORDINATEUR',intro='22 diagnostics • Choisissez un outil. Les résultats apparaissent dans la console. Les tests distants sont limités aux IPv4 privées.',target='IPv4 cible (appareil détecté ou IP privée)',select='OUTIL DE DIAGNOSTIC',port_hint='Ports TCP personnalisés (scan TCP, max. 32)',note_title='SÉCURITÉ ET LIMITES',note='Utilisez uniquement sur un réseau autorisé. Une absence de réponse ping ne signifie pas forcément hors ligne. Aucun vol de données ni télémétrie.',private_target='Entrez une adresse IPv4 privée valide (10.x, 172.16–31.x ou 192.168.x).',permission='Êtes-vous autorisé à tester cet appareil ?',ping='Ping ×4',dns='DNS inverse',trace='Traceroute',ports='Scanner les ports TCP',tcp_latency='Temps de connexion TCP',http_headers='En-têtes HTTP',tls='Certificat TLS (443)',host_detail='Détails IP et voisinage',subnet='Calcul de sous-réseau (/24)',ping_series='Latence (10 mesures)',system='Informations système',interfaces='Cartes réseau',ip_config='Configuration IP',arp_table='Cache ARP / voisins',route_table='Table de routage',connections='Connexions TCP/UDP',traffic='Trafic réseau instantané',dns_servers='Serveurs DNS configurés',wifi='Détails Wi-Fi',gateway='Passerelle par défaut',loopback='Test boucle locale',net_health='Bilan réseau local'),
'de':dict(remote='GERÄTETESTS',local='DIESER COMPUTER',intro='22 Diagnosen • Werkzeug wählen; Ergebnisse erscheinen in der Konsole. Remote-Tests nur für private IPv4.',target='Ziel-IPv4 (privat)',select='DIAGNOSEWERKZEUG',port_hint='Eigene TCP-Ports (max. 32)',note_title='SICHERHEIT',note='Nur autorisierte Netzwerke testen.',private_target='Gültige private IPv4-Adresse eingeben.',permission='Sind Sie zum Testen berechtigt?',ping='Ping ×4',dns='Reverse DNS',trace='Routenverfolgung',ports='TCP-Portscan',tcp_latency='TCP-Verbindungszeit',http_headers='HTTP-Header',tls='TLS-Zertifikat',host_detail='IP und Nachbarn',subnet='Subnetzberechnung',ping_series='Latenzreihe',system='Systemübersicht',interfaces='Netzwerkadapter',ip_config='IP-Konfiguration',arp_table='ARP-Tabelle',route_table='Routingtabelle',connections='TCP/UDP-Verbindungen',traffic='Netzwerkverkehr',dns_servers='DNS-Server',wifi='WLAN-Details',gateway='Standardgateway',loopback='Loopback-Test',net_health='Netzwerkbericht'),
'es':dict(remote='PRUEBAS DE EQUIPOS',local='ESTE EQUIPO',intro='22 diagnósticos • Elige una herramienta; resultados en consola. Pruebas remotas solo para IPv4 privadas.',target='IPv4 de destino privada',select='HERRAMIENTA',port_hint='Puertos TCP (máx. 32)',note_title='SEGURIDAD',note='Solo redes autorizadas.',private_target='Introduce una IPv4 privada válida.',permission='¿Tienes autorización para probar este equipo?',ping='Ping ×4',dns='DNS inverso',trace='Traceroute',ports='Escaneo de puertos TCP',tcp_latency='Latencia TCP',http_headers='Cabeceras HTTP',tls='Certificado TLS',host_detail='IP y vecinos',subnet='Cálculo de subred',ping_series='Serie de latencia',system='Resumen del sistema',interfaces='Adaptadores de red',ip_config='Configuración IP',arp_table='Caché ARP',route_table='Tabla de rutas',connections='Conexiones TCP/UDP',traffic='Tráfico de red',dns_servers='Servidores DNS',wifi='Detalles Wi-Fi',gateway='Puerta de enlace',loopback='Prueba de bucle local',net_health='Estado de red'),
'it':dict(remote='TEST DISPOSITIVO',local='QUESTO COMPUTER',intro='22 diagnostiche • Seleziona un test. Risultati nella console. Solo IPv4 private.',target='IPv4 di destinazione privata',select='STRUMENTO',port_hint='Porte TCP (max 32)',note_title='SICUREZZA',note='Solo reti autorizzate.',private_target='Inserisci un IPv4 privato valido.',permission='Sei autorizzato a testare questo dispositivo?',ping='Ping ×4',dns='DNS inverso',trace='Traceroute',ports='Scansione porte TCP',tcp_latency='Latenza TCP',http_headers='Intestazioni HTTP',tls='Certificato TLS',host_detail='IP e vicini',subnet='Calcolo sottorete',ping_series='Serie di latenza',system='Panoramica sistema',interfaces='Schede di rete',ip_config='Configurazione IP',arp_table='Cache ARP',route_table='Tabella routing',connections='Connessioni TCP/UDP',traffic='Traffico rete',dns_servers='Server DNS',wifi='Dettagli Wi-Fi',gateway='Gateway predefinito',loopback='Test loopback',net_health='Stato rete'),
'ja':dict(remote='デバイステスト',local='このコンピューター',intro='22種類の診断 • ツールを選択。結果はコンソールに表示。対象はプライベート IPv4 のみ。',target='対象プライベート IPv4',select='診断ツール',port_hint='TCPポート（最大32）',note_title='安全上の注意',note='許可されたネットワークのみ。',private_target='有効なプライベート IPv4 を入力してください。',permission='この機器をテストする権限がありますか？',ping='Ping ×4',dns='逆引き DNS',trace='経路追跡',ports='TCPポート検査',tcp_latency='TCP接続時間',http_headers='HTTPヘッダー',tls='TLS証明書',host_detail='IPと近隣情報',subnet='サブネット計算',ping_series='遅延測定',system='システム概要',interfaces='ネットワークアダプター',ip_config='IP設定',arp_table='ARPキャッシュ',route_table='ルート表',connections='TCP/UDP接続',traffic='ネットワーク通信量',dns_servers='DNSサーバー',wifi='Wi-Fi情報',gateway='デフォルトゲートウェイ',loopback='ループバック試験',net_health='ネットワーク診断'),
'ko':dict(remote='장치 테스트',local='내 컴퓨터',intro='22가지 진단 • 도구를 선택하세요. 결과는 콘솔에 표시됩니다. 사설 IPv4만 허용.',target='대상 사설 IPv4',select='진단 도구',port_hint='TCP 포트 (최대 32)',note_title='안전 안내',note='허가된 네트워크만 검사하세요.',private_target='올바른 사설 IPv4를 입력하세요.',permission='이 장치를 검사할 권한이 있나요?',ping='Ping ×4',dns='역방향 DNS',trace='경로 추적',ports='TCP 포트 검사',tcp_latency='TCP 연결 시간',http_headers='HTTP 헤더',tls='TLS 인증서',host_detail='IP 및 이웃',subnet='서브넷 계산',ping_series='지연 측정',system='시스템 정보',interfaces='네트워크 어댑터',ip_config='IP 구성',arp_table='ARP 캐시',route_table='라우팅 테이블',connections='TCP/UDP 연결',traffic='네트워크 트래픽',dns_servers='DNS 서버',wifi='Wi-Fi 정보',gateway='기본 게이트웨이',loopback='루프백 검사',net_health='네트워크 상태'),
'pt':dict(remote='TESTES DE DISPOSITIVOS',local='ESTE COMPUTADOR',intro='22 diagnósticos • Selecione um teste. Resultados no console. Apenas IPv4 privados.',target='IPv4 privado de destino',select='FERRAMENTA',port_hint='Portas TCP (máx. 32)',note_title='SEGURANÇA',note='Apenas redes autorizadas.',private_target='Digite um IPv4 privado válido.',permission='Você tem autorização para testar este dispositivo?',ping='Ping ×4',dns='DNS reverso',trace='Traceroute',ports='Verificar portas TCP',tcp_latency='Latência TCP',http_headers='Cabeçalhos HTTP',tls='Certificado TLS',host_detail='IP e vizinhos',subnet='Cálculo de sub-rede',ping_series='Série de latência',system='Visão do sistema',interfaces='Adaptadores de rede',ip_config='Configuração IP',arp_table='Cache ARP',route_table='Tabela de rotas',connections='Conexões TCP/UDP',traffic='Tráfego de rede',dns_servers='Servidores DNS',wifi='Detalhes Wi-Fi',gateway='Gateway padrão',loopback='Teste loopback',net_health='Saúde da rede'),
'ru':dict(remote='ТЕСТЫ УСТРОЙСТВ',local='ЭТОТ КОМПЬЮТЕР',intro='22 диагностики • Выберите инструмент. Результаты в консоли. Только частные IPv4.',target='Частный IPv4-адрес цели',select='ИНСТРУМЕНТ',port_hint='TCP-порты (макс. 32)',note_title='БЕЗОПАСНОСТЬ',note='Только разрешённые сети.',private_target='Введите корректный частный IPv4.',permission='У вас есть разрешение проверить это устройство?',ping='Ping ×4',dns='Обратный DNS',trace='Трассировка',ports='Проверка TCP-портов',tcp_latency='Задержка TCP',http_headers='HTTP-заголовки',tls='TLS-сертификат',host_detail='IP и соседи',subnet='Подсеть',ping_series='Замеры задержки',system='Обзор системы',interfaces='Сетевые адаптеры',ip_config='Настройки IP',arp_table='ARP-кэш',route_table='Маршруты',connections='TCP/UDP-соединения',traffic='Сетевой трафик',dns_servers='DNS-серверы',wifi='Данные Wi-Fi',gateway='Шлюз',loopback='Тест loopback',net_health='Состояние сети'),
'zh':dict(remote='设备测试',local='本机诊断',intro='22 项诊断 • 选择工具，结果显示在控制台。远程测试仅限私有 IPv4。',target='目标私有 IPv4',select='诊断工具',port_hint='TCP 端口（最多32个）',note_title='安全须知',note='仅测试授权网络。',private_target='请输入有效的私有 IPv4。',permission='您有权测试此设备吗？',ping='Ping ×4',dns='反向 DNS',trace='路由追踪',ports='TCP 端口扫描',tcp_latency='TCP 连接延迟',http_headers='HTTP 响应头',tls='TLS 证书',host_detail='IP 和邻居',subnet='子网计算',ping_series='延迟采样',system='系统概况',interfaces='网络适配器',ip_config='IP 配置',arp_table='ARP 缓存',route_table='路由表',connections='TCP/UDP 连接',traffic='网络流量',dns_servers='DNS 服务器',wifi='Wi-Fi 信息',gateway='默认网关',loopback='回环测试',net_health='网络健康检查'),
}

def _command(cmd, emit, timeout=12, max_lines=85):
    emit('$ ' + ' '.join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=timeout,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        lines = (p.stdout + '\n' + p.stderr).splitlines()
        for line in lines[:max_lines]:
            if line.strip(): emit('  ' + line)
        if len(lines)>max_lines: emit(f'  ... {len(lines)-max_lines} further lines omitted')
        emit(f'Exit code: {p.returncode}')
    except (OSError, subprocess.TimeoutExpired) as ex:
        emit(f'Command unavailable or timed out: {ex}', 'error')

def _default_gateway():
    # No third-party public-IP API. Read the route table locally.
    if os.name == 'nt':
        p = subprocess.run(['route','print','-4'],capture_output=True,text=True,errors='replace',timeout=8,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for ln in p.stdout.splitlines():
            cols=ln.split()
            if len(cols)>=4 and cols[0]=='0.0.0.0' and cols[1]=='0.0.0.0':
                return cols[2]
    else:
        p = subprocess.run(['ip','route','show','default'],capture_output=True,text=True,timeout=8)
        for line in p.stdout.splitlines():
            cols=line.split()
            if 'via' in cols: return cols[cols.index('via')+1]
    return None

def _fmt_bytes(n):
    for unit in ('B','KiB','MiB','GiB','TiB'):
        if abs(n)<1024: return f'{n:.1f} {unit}'
        n/=1024
    return f'{n:.1f} PiB'

def run_extra_tool(kind, ip, emit):
    if kind == 'system':
        emit(f'OS: {platform.platform()}')
        emit(f'Host: {socket.gethostname()}')
        emit(f'CPU logical threads: {psutil.cpu_count()}')
        emit(f'RAM total: {_fmt_bytes(psutil.virtual_memory().total)}')
        emit(f'Boot time: {datetime.fromtimestamp(psutil.boot_time()).isoformat(timespec="seconds")}')
    elif kind in ('interfaces','ip_config'):
        for name, addrs in psutil.net_if_addrs().items():
            stat=psutil.net_if_stats().get(name)
            emit(f'--- {name} / {"UP" if stat and stat.isup else "DOWN"} / {stat.speed if stat else "?"} Mbps ---')
            for addr in addrs:
                emit(f'  {addr.family.name if hasattr(addr.family,"name") else addr.family}: {addr.address} / mask={addr.netmask or "—"}')
        if kind == 'ip_config': _command(['ipconfig','/all'] if os.name=='nt' else ['ip','addr'],emit, max_lines=100)
    elif kind == 'arp_table':
        _command(['arp','-a'] if os.name=='nt' else ['ip','neigh','show'],emit)
    elif kind == 'route_table':
        _command(['route','print','-4'] if os.name=='nt' else ['ip','route'],emit)
    elif kind == 'connections':
        active=psutil.net_connections(kind='inet')
        emit('Local socket endpoints (maximum 70 shown):')
        for c in active[:70]:
            state=c.status or '—'
            emit(f'  {c.type.name if hasattr(c.type,"name") else c.type} {c.laddr} -> {c.raddr or "—"} [{state}] PID={c.pid or "—"}')
        emit(f'{len(active)} endpoints total; shown {min(70,len(active))}; some PID data may require admin.')
    elif kind == 'traffic':
        start=psutil.net_io_counters(pernic=True)
        time.sleep(2)
        end=psutil.net_io_counters(pernic=True)
        for name, data in end.items():
            old=start.get(name)
            if old:
                emit(f'{name}: down {_fmt_bytes((data.bytes_recv-old.bytes_recv)/2)}/s  up {_fmt_bytes((data.bytes_sent-old.bytes_sent)/2)}/s; total RX {_fmt_bytes(data.bytes_recv)} TX {_fmt_bytes(data.bytes_sent)}')
    elif kind == 'dns_servers':
        if os.name=='nt': _command(['ipconfig','/all'],emit, max_lines=110)
        else:
            try:
                for line in open('/etc/resolv.conf', encoding='utf-8'):
                    if line.strip(): emit(line.rstrip())
            except OSError as exc: emit(f'Resolver configuration unavailable: {exc}', 'error')
    elif kind == 'wifi':
        if os.name=='nt': _command(['netsh','wlan','show','interfaces'],emit)
        else: _command(['nmcli','-t','-f','ACTIVE,SSID,SIGNAL,FREQ','device','wifi'],emit)
    elif kind == 'gateway':
        gateway=_default_gateway()
        emit(f'Default gateway: {gateway or "not detected"}')
        if gateway:
            _command(['ping','-n','2','-w','900',gateway] if os.name=='nt' else ['ping','-c','2','-W','1',gateway],emit,8)
    elif kind == 'loopback':
        for host in ('127.0.0.1','localhost'):
            emit(f'Local resolver {host}: {socket.getaddrinfo(host,None)[0][4][0]}')
        _command(['ping','-n','2','127.0.0.1'] if os.name=='nt' else ['ping','-c','2','127.0.0.1'],emit,8)
    elif kind == 'net_health':
        emit(f'Hostname: {socket.gethostname()}')
        active=sum(1 for s in psutil.net_if_stats().values() if s.isup)
        emit(f'Active adapters: {active}')
        gateway=_default_gateway()
        emit(f'Default gateway: {gateway or "not detected"}')
        emit(f'Loopback DNS: {socket.gethostbyname("localhost")}')
        if gateway:
            try:
                ipaddress.IPv4Address(gateway)
                _command(['ping','-n','2','-w','900',gateway] if os.name=='nt' else ['ping','-c','2','-W','1',gateway],emit,8)
            except ValueError: pass
        emit('No external connectivity tests performed.')
    elif kind == 'tcp_latency':
        for port in (80,443,22,445,3389):
            before=time.monotonic()
            try:
                with socket.create_connection((ip,port),timeout=0.75): pass
                emit(f'{ip}:{port} CONNECT in {(time.monotonic()-before)*1000:.1f}ms','success')
            except OSError as exc:
                emit(f'{ip}:{port} not connected ({type(exc).__name__})')
    elif kind == 'http_headers':
        # HEAD request, no user-supplied URL or redirects to outside the private LAN.
        with socket.create_connection((ip,80),timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(f'HEAD / HTTP/1.0\r\nHost: {ip}\r\nConnection: close\r\n\r\n'.encode('ascii'))
            data=b''
            while b'\r\n\r\n' not in data and len(data)<8192:
                chunk=sock.recv(1024)
                if not chunk: break
                data+=chunk
            for line in data.split(b'\r\n\r\n')[0].decode('iso-8859-1','replace').splitlines()[:40]:
                emit(line)
    elif kind == 'tls':
        ctx=ssl.create_default_context()
        # This is inspection only: accept private devices with self-signed certs.
        ctx.check_hostname=False
        ctx.verify_mode=ssl.CERT_NONE
        with socket.create_connection((ip,443),timeout=3) as sock:
            sock.settimeout(3)
            with ctx.wrap_socket(sock, server_hostname=ip) as tls:
                emit(f'TLS version: {tls.version()}')
                emit(f'Cipher: {tls.cipher()}')
                cert=tls.getpeercert(binary_form=True)
                if cert:
                    import hashlib
                    emit(f'Certificate SHA256: {hashlib.sha256(cert).hexdigest()}')
                    emit('Certificate was NOT verified. Fingerprint only; trust not established.')
    elif kind == 'host_detail':
        target=ipaddress.IPv4Address(ip)
        emit(f'IP: {target}; private={target.is_private}; loopback={target.is_loopback}')
        emit(f'Reverse DNS: {socket.getfqdn(ip)}')
        net=ipaddress.ip_network(f'{ip}/24',strict=False)
        emit(f'Example /24 neighborhood: {net}')
    elif kind == 'subnet':
        net=ipaddress.ip_network(f'{ip}/24',strict=False)
        emit(f'Network: {net.network_address}')
        emit(f'Netmask: {net.netmask}')
        emit(f'Broadcast: {net.broadcast_address}')
        emit(f'Host range: {net.network_address+1} – {net.broadcast_address-1}')
        emit('Assumed /24 mask (not automatically discovered).')
    elif kind == 'ping_series':
        # Use ICMP via system utility; avoid platform-specific admin privileges.
        for i in range(10):
            start=time.monotonic()
            cmd=['ping','-n','1','-w','800',ip] if os.name=='nt' else ['ping','-c','1','-W','1',ip]
            try:
                p=subprocess.run(cmd,capture_output=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                emit(f'Sample {i+1}/10: {((time.monotonic()-start)*1000):.0f}ms wall clock' if p.returncode==0 else f'Sample {i+1}/10: timeout')
            except (OSError,subprocess.TimeoutExpired) as ex: emit(f'Sample {i+1}: {ex}')
    else:
        emit(f'Unsupported diagnostic: {kind}', 'error')
