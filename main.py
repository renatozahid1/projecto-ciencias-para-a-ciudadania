from flask import Flask, render_template_string, jsonify, request, session, redirect
import math
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "palapp_secret_key_super_segura_123"

# --- BASE DE DATOS EN MEMORIA ---
# Usuarios pre-registrados para pruebas. 
# La cuenta de la empresa predeterminada es "barbermoon", clave "123".
users_db = {
    "barbermoon": {
        "pwd": "123", "role": "empleador", "nombre": "Barbería Barber Moon", 
        "bio": "Expertos en cortes urbanos y clásicos.", "foto": "https://ui-avatars.com/api/?name=Barber+Moon&background=f59e0b&color=fff",
        "ubicacion": {"lat": -33.4489, "lon": -70.6693}, "streak": 5, "last_login": datetime.now().date()
    },
    "juanp": {
        "pwd": "123", "role": "candidato", "nombre": "Juan Pérez", "edad": 24,
        "bio": "Barbero con 3 años de experiencia.", "foto": "https://ui-avatars.com/api/?name=Juan+Perez&background=1f2937&color=fff",
        "habilidades": ["corte_cabello", "atencion_cliente"], "expectativa_renta": 600000,
        "streak": 2, "last_login": datetime.now().date()
    }
}

ofertas_db = [
    {
        "id": "job_101", "empleador_id": "barbermoon", "titulo": "Barbero / Estilista", 
        "empresa": "Barbería Barber Moon", "sueldo_ofrecido": 650000,
        "habilidades_requeridas": ["corte_cabello", "atencion_cliente"],
        "foto": "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=400&h=300&fit=crop"
    }
]

# Formato: {(emisor_id, receptor_id): "like" | "superlike" | "pass"}
swipes_db = {} 
# Formato: { "user1_user2": [mensajes...] }
chats_db = {}
# Historial para Rewind: { "user_id": [(target_id, action)] }
historial_swipes = {}

# --- LÓGICA DE SISTEMA ---
def actualizar_racha(username):
    user = users_db[username]
    hoy = datetime.now().date()
    if user["last_login"] == hoy - timedelta(days=1):
        user["streak"] = user.get("streak", 0) + 1
    elif user["last_login"] != hoy:
        user["streak"] = 1
    user["last_login"] = hoy

def get_match_id(u1, u2):
    return f"{u1}_{u2}" if u1 < u2 else f"{u2}_{u1}"

def check_match(cand_id, emp_id):
    # Un match ocurre si el candidato dio like/superlike al empleador (o su trabajo) 
    # y el empleador dio like/superlike al candidato.
    c_likes_e = swipes_db.get((cand_id, emp_id)) in ["like", "superlike"]
    e_likes_c = swipes_db.get((emp_id, cand_id)) in ["like", "superlike"]
    
    if c_likes_e and e_likes_c:
        match_id = get_match_id(cand_id, emp_id)
        if match_id not in chats_db:
            chats_db[match_id] = [{
                "emisor": "sistema", "nombre_emisor": "PalApp",
                "texto": "🎉 ¡Es un Match! Ya pueden conversar.",
                "hora": datetime.now().strftime("%H:%M")
            }]
        return True
    return False

# --- FRONTEND COMPONENTES ---
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
        .blur-sm { filter: blur(4px); }
    </style>
</head>
"""

HTML_AUTH = f"""
<!DOCTYPE html><html lang="es">{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen flex flex-col justify-center items-center px-4">
    <div class="w-full max-w-sm bg-gray-900 p-6 rounded-2xl border border-gray-800 shadow-xl">
        <div class="text-center mb-6">
            <div class="w-16 h-16 bg-amber-500 rounded-full flex items-center justify-center text-3xl mx-auto mb-2 shadow-lg shadow-amber-500/20">⚡</div>
            <h1 class="text-2xl font-extrabold tracking-tight">PalApp</h1>
        </div>
        
        <form onsubmit="login(event)" id="loginForm" class="space-y-4">
            <input id="user" placeholder="Usuario (ej: barbermoon)" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:border-amber-500 outline-none">
            <input id="pwd" type="password" placeholder="Contraseña (123)" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:border-amber-500 outline-none">
            <button type="submit" class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-gray-950 font-bold rounded-xl transition">Ingresar</button>
        </form>
        
        <div class="mt-6 border-t border-gray-800 pt-4">
            <p class="text-xs text-gray-400 text-center mb-2">¿No tienes cuenta?</p>
            <div class="flex gap-2">
                <button onclick="register('candidato')" class="flex-1 py-2 bg-gray-800 rounded-lg text-xs font-semibold">Soy Candidato</button>
                <button onclick="register('empleador')" class="flex-1 py-2 bg-gray-800 rounded-lg text-xs font-semibold">Soy Empresa</button>
            </div>
        </div>
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
    async function register(role) {{
        let u = document.getElementById('user').value;
        let p = document.getElementById('pwd').value;
        if(!u || !p) return alert("Llena los campos arriba primero");
        let r = await fetch('/api/register', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{user: u, pwd: p, role: role}})
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
        <div class="flex items-center gap-2">
            <span class="text-amber-500 font-bold">🔥 {{{{ user.streak }}}} días</span>
        </div>
        <div class="text-xs text-gray-400">
            <span class="blur-sm bg-gray-800 px-2 py-1 rounded-full text-white">{{{{ pending_likes }}}} Les gustas</span>
        </div>
    </div>

    <div class="max-w-sm mx-auto relative h-[65vh]" id="card-container">
        <!-- Tarjeta dinámica -->
    </div>

    <div class="max-w-sm mx-auto flex justify-center gap-4 mt-6 z-10 relative">
        <button onclick="rewind()" class="w-12 h-12 bg-gray-800 text-yellow-500 rounded-full text-xl shadow-lg hover:bg-gray-700 transition">↩</button>
        <button onclick="action('pass')" class="w-14 h-14 bg-gray-900 border-2 border-red-500/50 text-red-500 rounded-full text-2xl shadow-lg hover:bg-red-500/20 transition">❌</button>
        <button onclick="action('superlike')" class="w-12 h-12 bg-gray-800 text-blue-500 rounded-full text-xl shadow-lg hover:bg-gray-700 transition">⭐</button>
        <button onclick="action('like')" class="w-14 h-14 bg-amber-500 text-gray-950 rounded-full text-2xl shadow-lg shadow-amber-500/20 hover:bg-amber-400 transition">💚</button>
    </div>

    <!-- Match Overlay -->
    <div id="match-screen" class="match-overlay fixed inset-0 flex flex-col justify-center items-center text-center p-6">
        <h1 class="text-5xl font-extrabold text-amber-500 mb-2 font-serif italic">¡Es un Match! 🎉</h1>
        <p class="text-gray-300 mb-8">Ustedes se han gustado mutuamente.</p>
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
            container.innerHTML = '<div class="h-full bg-gray-900 rounded-2xl border border-gray-800 flex flex-col items-center justify-center text-center p-6"><span class="text-4xl mb-4">📭</span><h3 class="font-bold text-lg">No hay más perfiles</h3><p class="text-sm text-gray-400 mt-2">Vuelve más tarde para ver nuevos candidatos o empresas.</p></div>';
            return;
        }}

        currentItem = queue[0];
        const tags = currentItem.habilidades ? currentItem.habilidades.map(h => `<span class="bg-gray-800/80 backdrop-blur text-gray-200 text-[10px] px-2 py-1 rounded-md border border-gray-700">#${{h}}</span>`).join('') : '';
        
        container.innerHTML = `
            <div id="swipe-card" class="card-drag absolute inset-0 bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col bg-cover bg-center" style="background-image: linear-gradient(to top, rgba(3,7,18,1) 0%, rgba(3,7,18,0.4) 50%, rgba(3,7,18,0) 100%), url('${{currentItem.foto}}')">
                <div class="mt-auto p-5 relative z-10">
                    <h2 class="text-2xl font-extrabold text-white mb-1 shadow-black drop-shadow-md">${{currentItem.titulo || currentItem.nombre}} <span class="text-lg font-normal text-gray-300">${{currentItem.edad || ''}}</span></h2>
                    <p class="text-amber-500 font-medium text-sm mb-3 drop-shadow-md">${{currentItem.empresa || currentItem.expectativa_renta ? 'Sueldo: $'+(currentItem.sueldo_ofrecido || currentItem.expectativa_renta).toLocaleString('es-CL') : ''}}</p>
                    <p class="text-sm text-gray-200 mb-4 line-clamp-2">${{currentItem.bio}}</p>
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
            const rotate = currentX * 0.05;
            el.style.transform = `translateX(${{currentX}}px) rotate(${{rotate}}deg)`;
        }};
        const end = () => {{
            isDragging = false;
            if (currentX > 100) action('like');
            else if (currentX < -100) action('pass');
            else {{
                el.style.transition = 'transform 0.3s ease';
                el.style.transform = '';
            }}
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
        
        // Animación de salida
        if(cardEl) {{
            cardEl.style.transition = 'transform 0.4s ease, opacity 0.4s ease';
            const offset = type === 'pass' ? -400 : (type === 'superlike' ? 0 : 400);
            const yOffset = type === 'superlike' ? -400 : 0;
            cardEl.style.transform = `translate(${{offset}}px, ${{yOffset}}px) rotate(${{offset*0.1}}deg)`;
            cardEl.style.opacity = '0';
        }}

        let target_id = currentItem.id;
        
        // Eliminar visualmente primero para fluidez
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

    function nextCard() {{
        queue.shift();
        renderCard();
    }}

    async function rewind() {{
        let r = await fetch('/api/rewind', {{method: 'POST'}});
        let res = await r.json();
        if(res.status === 'ok') {{ loadFeed(); }} else {{ alert(res.msg); }}
    }}

    loadFeed();
    </script>
</body></html>
"""

# --- RUTAS DE FLASK ---
@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/feed")
    return render_template_string(HTML_AUTH)

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    u = data.get("user")
    p = data.get("pwd")
    if u in users_db and users_db[u]["pwd"] == p:
        session["user_id"] = u
        actualizar_racha(u)
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "msg": "Credenciales inválidas"}), 401

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.json
    u = data.get("user")
    p = data.get("pwd")
    r = data.get("role")
    
    if u in users_db:
        return jsonify({"status": "error", "msg": "Usuario ya existe"}), 400
        
    users_db[u] = {
        "pwd": p, "role": r, "nombre": f"Usuario {u}", "bio": "",
        "foto": f"https://ui-avatars.com/api/?name={u}&background=random",
        "streak": 1, "last_login": datetime.now().date(), "habilidades": []
    }
    session["user_id"] = u
    return jsonify({"status": "ok"})

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")

@app.route("/feed")
def vista_feed():
    u = session.get("user_id")
    if not u or u not in users_db: return redirect("/")
    
    user = users_db[u]
    # Calcular likes pendientes (gente que te dio like y aún no respondes)
    pending = sum(1 for (emisor, receptor), action in swipes_db.items() 
                  if receptor == u and action in ["like", "superlike"] 
                  and swipes_db.get((u, emisor)) is None)
                  
    return render_template_string(HTML_FEED, user=user, pending_likes=pending)

@app.route("/api/feed", methods=["GET"])
def get_feed():
    u = session.get("user_id")
    user = users_db[u]
    res = []
    
    if user["role"] == "candidato":
        # Mostrar ofertas que el candidato NO ha swipeado
        for o in ofertas_db:
            if (u, o["empleador_id"]) not in swipes_db:
                res.append({"id": o["empleador_id"], **o})
    else:
        # Mostrar candidatos que el empleador NO ha swipeado
        for cand_id, cand_data in users_db.items():
            if cand_data["role"] == "candidato" and (u, cand_id) not in swipes_db:
                res.append({"id": cand_id, **cand_data})
                
    return jsonify(res)

@app.route("/api/swipe", methods=["POST"])
def handle_swipe():
    u = session.get("user_id")
    data = request.json
    target = data.get("target_id")
    action = data.get("type") # pass, like, superlike
    
    # Guardar swipe
    swipes_db[(u, target)] = action
    
    # Historial para Rewind
    if u not in historial_swipes:
        historial_swipes[u] = []
    historial_swipes[u].append((target, action))
    if len(historial_swipes[u]) > 5:
        historial_swipes[u].pop(0)

    # Revisar Match bidireccional
    is_match = False
    if action in ["like", "superlike"]:
        is_match = check_match(u, target) if users_db[u]["role"] == "candidato" else check_match(target, u)

    return jsonify({"status": "ok", "is_match": is_match})

@app.route("/api/rewind", methods=["POST"])
def handle_rewind():
    u = session.get("user_id")
    hist = historial_swipes.get(u, [])
    if not hist:
        return jsonify({"status": "error", "msg": "No hay acciones para deshacer"})
    
    last_target, _ = hist.pop()
    # Eliminar swipe
    if (u, last_target) in swipes_db:
        del swipes_db[(u, last_target)]
        
    return jsonify({"status": "ok"})

# Vistas mínimas para Chats y Perfil para completar la navegación
@app.route("/chats")
def vista_chats():
    if "user_id" not in session: return redirect("/")
    u = session["user_id"]
    mis_chats = []
    for match_id, msgs in chats_db.items():
        if u in match_id.split("_"):
            otro_id = match_id.replace(u, "").replace("_", "")
            mis_chats.append({
                "nombre": users_db[otro_id]["nombre"],
                "foto": users_db[otro_id]["foto"],
                "ultimo_msg": msgs[-1]["texto"]
            })
    html = f"""<!DOCTYPE html><html lang="es">{HTML_HEAD}
    <body class="bg-gray-950 text-white min-h-screen p-4 pb-20">
        <h1 class="text-2xl font-bold mb-4">Mensajes</h1>
        <div class="space-y-4">
            {''.join([f'<div class="flex items-center gap-4 bg-gray-900 p-4 rounded-xl border border-gray-800"><img src="{c["foto"]}" class="w-12 h-12 rounded-full"><div class="flex-1"><h3 class="font-bold">{c["nombre"]}</h3><p class="text-sm text-gray-400">{c["ultimo_msg"]}</p></div></div>' for c in mis_chats])}
            { '<p class="text-gray-500 mt-10 text-center">Aún no tienes matches. ¡Sigue swipeando!</p>' if not mis_chats else '' }
        </div>
        {NAV_BAR}
    </body></html>"""
    return render_template_string(html)

@app.route("/perfil")
def vista_perfil():
    if "user_id" not in session: return redirect("/")
    u = session["user_id"]
    user = users_db[u]
    html = f"""<!DOCTYPE html><html lang="es">{HTML_HEAD}
    <body class="bg-gray-950 text-white min-h-screen p-4 pb-20 flex flex-col items-center pt-10">
        <img src="{user['foto']}" class="w-28 h-28 rounded-full border-4 border-amber-500 mb-4 object-cover">
        <h1 class="text-2xl font-bold">{user['nombre']}</h1>
        <p class="text-amber-500 text-sm mb-4 capitalize">{user['role']}</p>
        <div class="bg-gray-900 p-4 rounded-xl border border-gray-800 w-full max-w-sm mb-4 text-center">
            <p class="text-gray-300 italic">"{user['bio']}"</p>
        </div>
        <a href="/logout" class="py-3 px-10 border border-red-500/50 text-red-500 font-bold rounded-xl hover:bg-red-500/10 transition mt-4">Cerrar Sesión</a>
        {NAV_BAR}
    </body></html>"""
    return render_template_string(html)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
