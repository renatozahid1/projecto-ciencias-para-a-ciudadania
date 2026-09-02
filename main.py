from flask import Flask, render_template_string, jsonify, request, session, redirect
import math
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = "palapp_secret_key_super_segura_123"

# --- BASE DE DATOS EN MEMORIA ---
users_db = {
    "barbermoon": {
        "pwd": "123", "role": "empleador", "nombre": "Barbería Barber Moon", 
        "ubicacion": {"lat": -33.4489, "lon": -70.6693}, "contacto": "+56912345678",
        "foto": "https://ui-avatars.com/api/?name=Barber+Moon&background=f59e0b&color=fff"
    },
    "juanp": {
        "pwd": "123", "role": "candidato", "nombre": "Juan Pérez", "edad": 24,
        "ubicacion": {"lat": -33.4489, "lon": -70.6693}, "expectativa_renta": 600000,
        "habilidades": ["corte_cabello", "atencion_cliente"],
        "foto": "https://ui-avatars.com/api/?name=Juan+Perez&background=1f2937&color=fff"
    }
}

ofertas_db = [
    {
        "id": "job_102", "empleador_id": "barbermoon", "titulo": "Barbero / Estilista",
        "empresa": "Barbería Barber Moon", "edad_minima": 20,
        "ubicacion": {"lat": -33.4489, "lon": -70.6693},
        "habilidades_requeridas": ["corte_cabello", "atencion_cliente"],
        "sueldo_ofrecido": 650000,
        "foto": "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=400&h=300&fit=crop"
    }
]

# (usuario_id, target_id): "like" | "pass"
swipes_db = {}
chats_db = {}

# --- LÓGICA DE MATCH (TU ALGORITMO) ---
def calcular_match(cand, emp):
    if cand.get("edad", 0) < emp.get("edad_minima", 18):
        return 0.0
    cand_skills = set(cand.get("habilidades", []))
    req_skills = set(emp.get("habilidades_requeridas", []))
    s_skills = len(cand_skills.intersection(req_skills)) / len(req_skills) if req_skills else 1.0
    
    cand_loc = cand.get("ubicacion", {"lat": -33.4489, "lon": -70.6693})
    emp_loc = emp.get("ubicacion", {"lat": -33.4489, "lon": -70.6693})
    dlat = math.radians(emp_loc["lat"] - cand_loc["lat"])
    dlon = math.radians(emp_loc["lon"] - cand_loc["lon"])
    a = math.sin(dlat/2)**2 + math.cos(math.radians(cand_loc["lat"])) * math.cos(math.radians(emp_loc["lat"])) * math.sin(dlon/2)**2
    dist_km = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    s_dist = math.exp(-0.08 * dist_km)
    
    sueldo_emp = emp.get("sueldo_ofrecido", 0)
    exp_cand = cand.get("expectativa_renta", 1) or 1
    s_sal = 1.0 if sueldo_emp >= exp_cand else (sueldo_emp / exp_cand)
    return round((0.45 * s_skills + 0.35 * s_dist + 0.20 * s_sal) * 100, 1)

def check_match_mutuo(cand_id, emp_id):
    # Match bidireccional
    c_likes_e = swipes_db.get((cand_id, emp_id)) == "like"
    e_likes_c = swipes_db.get((emp_id, cand_id)) == "like"
    
    if c_likes_e and e_likes_c:
        chat_key = f"{cand_id}_{emp_id}"
        if chat_key not in chats_db:
            chats_db[chat_key] = [{
                "emisor": "sistema", "nombre_emisor": "PalApp",
                "texto": "🎉 ¡Es un Match Mutuo! Ya pueden conversar.",
                "hora": datetime.now().strftime("%H:%M")
            }]
        return True
    return False

# --- COMPONENTES FRONTEND ---
NAV_BAR = """
<nav class="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 flex justify-around py-3 text-xs text-gray-400 z-50">
    <a href="/feed" class="flex flex-col items-center hover:text-amber-500"><span class="text-lg">🔥</span>Swipe</a>
    <a href="/chats" class="flex flex-col items-center hover:text-amber-500"><span class="text-lg">💬</span>Chats</a>
    <a href="/perfil" class="flex flex-col items-center hover:text-amber-500"><span class="text-lg">👤</span>Perfil</a>
</nav>
"""

HTML_HEAD = """
<head>
    <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
    <title>PalApp</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .card-drag { transition: transform 0.2s ease, opacity 0.2s ease; cursor: grab; }
        .card-drag:active { cursor: grabbing; transition: none; }
        .match-overlay { display: none; background: rgba(0,0,0,0.9); z-index: 100; }
    </style>
</head>
"""

HTML_AUTH = f"""
<!DOCTYPE html><html lang="es">{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen flex flex-col justify-center items-center px-4">
    <div class="w-full max-w-sm text-center mb-6">
        <div class="w-20 h-20 bg-amber-500 rounded-full flex items-center justify-center text-4xl mx-auto mb-4 shadow-lg shadow-amber-500/20">⚡</div>
        <h1 class="text-3xl font-extrabold tracking-tight">PalApp</h1>
        <p class="text-gray-400 text-sm mt-1">Conecta el talento con las empresas</p>
    </div>
    <div class="w-full max-w-sm bg-gray-900 p-6 rounded-2xl border border-gray-800 shadow-xl">
        <form onsubmit="login(event)" id="loginForm" class="space-y-4">
            <input id="user" placeholder="Usuario (ej: barbermoon o juanp)" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:border-amber-500 outline-none">
            <input id="pwd" type="password" placeholder="Contraseña (123)" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:border-amber-500 outline-none">
            <button type="submit" class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-gray-950 font-bold rounded-xl transition">Ingresar</button>
        </form>
    </div>
    <script>
    async function login(e) {{
        e.preventDefault();
        let r = await fetch('/api/login', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{user: document.getElementById('user').value, pwd: document.getElementById('pwd').value}})
        }});
        let res = await r.json();
        if(res.status === 'ok') location.href = '/feed'; else alert(res.msg);
    }}
    </script>
</body></html>
"""

HTML_FEED = f"""
<!DOCTYPE html><html lang="es">{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen pb-20 px-4 pt-6 overflow-hidden">
    <div class="max-w-sm mx-auto flex justify-between items-center mb-4">
        <h2 class="text-xl font-bold">🔥 Descubrir</h2>
        <span class="bg-gray-800 px-2 py-1 rounded-lg text-xs capitalize">{{{{ user.role }}}}</span>
    </div>

    <div class="max-w-sm mx-auto relative h-[65vh]" id="card-container">
        <!-- Tarjeta dinámica -->
    </div>

    <div class="max-w-sm mx-auto flex justify-center gap-6 mt-6 z-10 relative">
        <button onclick="action('pass')" class="w-16 h-16 bg-gray-900 border-2 border-red-500/50 text-red-500 rounded-full text-3xl shadow-lg hover:bg-red-500/20 transition">❌</button>
        <button onclick="action('like')" class="w-16 h-16 bg-amber-500 text-gray-950 rounded-full text-3xl shadow-lg shadow-amber-500/20 hover:bg-amber-400 transition">💚</button>
    </div>

    <!-- Match Overlay -->
    <div id="match-screen" class="match-overlay fixed inset-0 flex flex-col justify-center items-center text-center p-6">
        <h1 class="text-5xl font-extrabold text-amber-500 mb-2 font-serif italic">¡Match! 🎉</h1>
        <p class="text-gray-300 mb-8">El interés es mutuo.</p>
        <div class="flex gap-4 mb-8">
            <img src="{{{{ user.foto }}}}" class="w-24 h-24 rounded-full border-4 border-amber-500 object-cover">
            <img id="match-img" src="" class="w-24 h-24 rounded-full border-4 border-amber-500 object-cover">
        </div>
        <button onclick="location.href='/chats'" class="w-full max-w-xs py-4 bg-amber-500 text-gray-950 font-bold rounded-xl mb-3">Ir al Chat</button>
        <button onclick="document.getElementById('match-screen').style.display='none'; nextCard();" class="w-full max-w-xs py-4 bg-transparent border border-gray-600 text-white font-bold rounded-xl">Seguir buscando</button>
    </div>

    {NAV_BAR}

    <script>
    let queue = [];
    let currentItem = null;
    let cardEl = null;

    async function loadFeed() {{
        let r = await fetch('/api/feed');
        queue = await r.json();
        renderCard();
    }}

    function renderCard() {{
        const container = document.getElementById('card-container');
        if (queue.length === 0) {{
            container.innerHTML = '<div class="h-full bg-gray-900 rounded-2xl border border-gray-800 flex flex-col items-center justify-center text-center p-6"><span class="text-4xl mb-4">📭</span><h3 class="font-bold text-lg">No hay más perfiles</h3></div>';
            return;
        }}

        currentItem = queue[0];
        const tags = (currentItem.habilidades || currentItem.habilidades_requeridas || []).map(h => `<span class="bg-gray-800 text-gray-300 text-[10px] px-2 py-1 rounded">#${{h}}</span>`).join('');
        const sueldo_texto = currentItem.sueldo_ofrecido ? `$${{currentItem.sueldo_ofrecido.toLocaleString('es-CL')}}` : `$${{currentItem.expectativa_renta.toLocaleString('es-CL')}} (Exp)`;
        
        container.innerHTML = `
            <div id="swipe-card" class="card-drag absolute inset-0 bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col bg-cover bg-center" style="background-image: linear-gradient(to top, rgba(3,7,18,1) 0%, rgba(3,7,18,0.7) 40%, rgba(3,7,18,0) 100%), url('${{currentItem.foto}}')">
                <div class="mt-auto p-5 relative z-10">
                    <div class="flex justify-between items-end mb-2">
                        <span class="bg-amber-500 text-gray-950 text-xs px-2.5 py-1 rounded-full font-bold shadow-lg">${{currentItem.match_score}}% Match Algorítmico</span>
                    </div>
                    <h2 class="text-2xl font-extrabold text-white mb-1 shadow-black">${{currentItem.titulo || currentItem.nombre}} <span class="text-lg font-normal text-gray-300">${{currentItem.edad || ''}}</span></h2>
                    <p class="text-amber-500 font-medium text-sm mb-3 drop-shadow-md">${{currentItem.empresa || ''}} | ${{sueldo_texto}}</p>
                    <div class="flex flex-wrap gap-1.5">${{tags}}</div>
                </div>
            </div>
        `;
        
        cardEl = document.getElementById('swipe-card');
        setupGestures(cardEl);
    }}

    function setupGestures(el) {{
        let isDragging = false, startX = 0, currentX = 0;
        const start = (x) => {{ isDragging = true; startX = x; el.style.transition = 'none'; }};
        const move = (x) => {{
            if (!isDragging) return;
            currentX = x - startX;
            el.style.transform = `translateX(${{currentX}}px) rotate(${{currentX * 0.05}}deg)`;
        }};
        const end = () => {{
            isDragging = false;
            if (currentX > 100) action('like');
            else if (currentX < -100) action('pass');
            else {{ el.style.transition = 'transform 0.3s ease'; el.style.transform = ''; }}
            currentX = 0;
        }};
        el.addEventListener('touchstart', e => start(e.touches[0].clientX));
        el.addEventListener('touchmove', e => move(e.touches[0].clientX));
        el.addEventListener('touchend', end);
        el.addEventListener('mousedown', e => start(e.clientX));
        window.addEventListener('mousemove', e => move(e.clientX));
        window.addEventListener('mouseup', () => {{ if(isDragging) end(); }});
    }}

    async function action(type) {{
        if (!currentItem) return;
        if(cardEl) {{
            cardEl.style.transition = 'transform 0.4s ease, opacity 0.4s ease';
            const offset = type === 'pass' ? -400 : 400;
            cardEl.style.transform = `translate(${{offset}}px, 0px) rotate(${{offset*0.1}}deg)`;
            cardEl.style.opacity = '0';
        }}
        
        let target_id = currentItem.id;
        setTimeout(() => {{ nextCard(); }}, 300);

        let r = await fetch('/api/swipe', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{target_id: target_id, type: type}})
        }});
        let res = await r.json();
        
        if (res.is_match) {{
            document.getElementById('match-img').src = currentItem.foto;
            document.getElementById('match-screen').style.display = 'flex';
        }}
    }}

    function nextCard() {{ queue.shift(); renderCard(); }}
    loadFeed();
    </script>
</body></html>
"""

# --- RUTAS ---
@app.route("/")
def index():
    if "user_id" in session: return redirect("/feed")
    return render_template_string(HTML_AUTH)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    u, p = data.get("user"), data.get("pwd")
    if u in users_db and users_db[u]["pwd"] == p:
        session["user_id"] = u
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "msg": "Credenciales inválidas"}), 401

@app.route("/feed")
def vista_feed():
    u = session.get("user_id")
    if not u or u not in users_db: return redirect("/")
    return render_template_string(HTML_FEED, user=users_db[u])

@app.route("/api/feed", methods=["GET"])
def get_feed():
    u = session.get("user_id")
    user = users_db[u]
    res = []
    
    if user["role"] == "candidato":
        for o in ofertas_db:
            if (u, o["empleador_id"]) not in swipes_db:
                item = dict(o)
                item["id"] = o["empleador_id"]
                item["match_score"] = calcular_match(user, o)
                res.append(item)
    else:
        # Perfil base de la oferta del empleador para calcular el match con los candidatos
        mis_ofertas = [o for o in ofertas_db if o["empleador_id"] == u]
        oferta_base = mis_ofertas[0] if mis_ofertas else {}

        for cand_id, cand_data in users_db.items():
            if cand_data.get("role") == "candidato" and (u, cand_id) not in swipes_db:
                item = dict(cand_data)
                item["id"] = cand_id
                item["match_score"] = calcular_match(cand_data, oferta_base)
                res.append(item)
                
    res.sort(key=lambda x: x["match_score"], reverse=True)
    return jsonify(res)

@app.route("/api/swipe", methods=["POST"])
def handle_swipe():
    u = session.get("user_id")
    target = request.json.get("target_id")
    action = request.json.get("type")
    
    swipes_db[(u, target)] = action
    
    is_match = False
    if action == "like":
        user_role = users_db[u]["role"]
        cand_id = u if user_role == "candidato" else target
        emp_id = target if user_role == "candidato" else u
        is_match = check_match_mutuo(cand_id, emp_id)

    return jsonify({"status": "ok", "is_match": is_match})

# Vistas de Chats y Perfil simplificadas para mantener la navegación intacta
@app.route("/chats")
def vista_chats():
    u = session.get("user_id")
    mis_chats = []
    for chat_key in chats_db:
        if u in chat_key.split("_"):
            otro_id = chat_key.replace(u, "").replace("_", "")
            mis_chats.append({"nombre": users_db[otro_id]["nombre"]})
    html = f"""<!DOCTYPE html><html lang="es">{HTML_HEAD}
    <body class="bg-gray-950 text-white min-h-screen p-4 pb-20">
        <h1 class="text-2xl font-bold mb-4">Mensajes</h1>
        <div class="space-y-4">
            {''.join([f'<div class="bg-gray-900 p-4 rounded-xl border border-gray-800"><h3 class="font-bold">{c["nombre"]}</h3></div>' for c in mis_chats])}
            { '<p class="text-gray-500 text-center">Solo los matches mutuos aparecen aquí.</p>' if not mis_chats else '' }
        </div>
        {NAV_BAR}
    </body></html>"""
    return render_template_string(html)

@app.route("/perfil")
def vista_perfil():
    user = users_db[session.get("user_id")]
    html = f"""<!DOCTYPE html><html lang="es">{HTML_HEAD}
    <body class="bg-gray-950 text-white min-h-screen p-4 pb-20 flex flex-col items-center pt-10">
        <img src="{user['foto']}" class="w-28 h-28 rounded-full border-4 border-amber-500 mb-4 object-cover">
        <h1 class="text-2xl font-bold">{user['nombre']}</h1>
        <p class="text-amber-500 text-sm mb-4 capitalize">{user['role']}</p>
        <a href="/logout" class="py-3 px-10 border border-red-500/50 text-red-500 font-bold rounded-xl hover:bg-red-500/10 transition mt-4">Cerrar Sesión</a>
        {NAV_BAR}
    </body></html>"""
    return render_template_string(html)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
