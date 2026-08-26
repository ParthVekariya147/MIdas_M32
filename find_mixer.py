"""
find_mixer.py  -  Network par MIDAS M32 / X32 aapoaap shodhe chhe.

Aakha network ma "koi mixer chhe?" evo sandesho moklé chhe ane
je jawab aape teno IP address batave chhe.
Pachhi te IP config.json ma save kari aape chhe.
"""

import socket
import sys
import time

import m32_core as core
import osc_lite

core.setup_console()

PORT = 10023
LINE = "=" * 62


def local_ips():
    """Aa PC na badha IPv4 address."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def broadcast_targets():
    """Badha broadcast address + common M32 default subnets."""
    targets = ["255.255.255.255"]
    for ip in local_ips():
        parts = ip.split(".")
        if len(parts) == 4:
            targets.append("%s.%s.%s.255" % (parts[0], parts[1], parts[2]))
    for extra in ("192.168.1.255", "192.168.0.255", "192.168.31.255",
                  "10.0.0.255", "172.16.0.255"):
        if extra not in targets:
            targets.append(extra)
    return targets


def scan(seconds=4.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.25)

    found = {}
    end = time.time() + seconds
    next_send = 0.0

    while time.time() < end:
        if time.time() >= next_send:
            for target in broadcast_targets():
                for address in ("/info", "/xinfo"):
                    try:
                        sock.sendto(osc_lite.build_message(address), (target, PORT))
                    except OSError:
                        pass
            next_send = time.time() + 1.0
            sys.stdout.write(".")
            sys.stdout.flush()

        try:
            data, src = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            continue

        for address, args in osc_lite.parse_message(data):
            if address in ("/info", "/xinfo"):
                strings = [a for a in args if isinstance(a, str)]
                ip = src[0]
                entry = found.get(ip, {})
                if address == "/info" and len(strings) >= 4:
                    entry["name"] = strings[1]
                    entry["model"] = strings[2]
                    entry["firmware"] = strings[3]
                elif address == "/xinfo" and len(strings) >= 4:
                    entry.setdefault("name", strings[1])
                    entry.setdefault("model", strings[2])
                    entry.setdefault("firmware", strings[3])
                found[ip] = entry

    sock.close()
    return found


def main():
    print(LINE)
    print("   MIXER SHODHO  (Network Scan)")
    print(LINE)
    print("  Aa PC na IP address : %s" % (", ".join(local_ips()) or "koi nahi"))
    print("  Network par mixer shodhu chhu, 5 second raah juo", end="")
    sys.stdout.flush()

    found = scan(5.0)
    print("\n" + LINE)

    if not found:
        print("  [X] Koi mixer na malyu.")
        print()
        print("  AA CHECK KARO:")
        print("   1. LAN cable mixer na 'REMOTE' port ma bharayelo chhe?")
        print("   2. Mixer chalu chhe? (Setup -> Network ma IP dekhay chhe?)")
        print("   3. Direct cable hoy to: PC nu IP mixer na j subnet ma hovu joiye.")
        print("      dakhla: mixer 192.168.1.15 -> PC 192.168.1.10 (mask 255.255.255.0)")
        print("   4. Windows Firewall aa program ne allow kare chhe?")
        print("   5. Mixer ma Setup -> Network -> IP address jate joi ne")
        print("      config.json ma 'mixer_ip' ma lakhi do.")
        print(LINE)
        return

    ips = sorted(found.keys())
    print("  [OK] %d mixer malyu:" % len(ips))
    print()
    for i, ip in enumerate(ips, 1):
        d = found[ip]
        print("   %d) %-15s  %s  |  %s  |  firmware %s"
              % (i, ip, d.get("name", "?"), d.get("model", "?"),
                 d.get("firmware", "?")))
    print()
    print(LINE)

    choice = ips[0]
    if len(ips) > 1:
        try:
            n = input("  Kayo vaparvo chhe? (1-%d, Enter = 1): " % len(ips)).strip()
            if n:
                choice = ips[int(n) - 1]
        except (ValueError, IndexError, EOFError):
            choice = ips[0]

    try:
        ans = input("  '%s' ne config.json ma save karu? (y/n, Enter = y): "
                    % choice).strip().lower()
    except EOFError:
        ans = "y"

    if ans in ("", "y", "yes"):
        core.save_config({"mixer_ip": choice})
        print("  [OK] config.json ma mixer_ip = %s save thai gayu!" % choice)
        print("  Have  2-METER-SCAN.bat  chalavo.")
    else:
        print("  Kai save karyu nathi.")
    print(LINE)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Band karyu.")
