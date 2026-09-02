from flask import Flask, render_template_string, jsonify, request, session
import math
import uuid
from datetime import datetime

app = Flask(__name__)
# Clave secreta necesaria para mantener sesiones independientes por dispositivo
app.secret_key = "palapp_secret_key_super_segura_123"

# Base de datos en memoria indexada por ID de dispositivo/usuario
candidatos_db = {}
chats_db = {}  # Formato: { "user_id_job_id": [mensajes...] }

perfil_empleador = {
    "nombre_empresa": "Barbería Barber Moon",
    "rut_empresa": "77.123.456-K",
    "contacto": "+56912345678",
    "ubicacion": {"lat": -33.4489, "lon": -70.6693}
}

ofertas = [
    {
        "id": "job_101",
        "titulo": "Cajero / Atención al Cliente",
        "empresa": "Retail Express",
        "edad_minima": 18,
        "ubicacion": {"lat": -33.4560, "lon": -70.6480},
        "habilidades_requeridas": ["atencion_cliente", "caja"],
        "sueldo_ofrecido": 600000
    },
    {
        "id": "job_102",
        "titulo": "Barbero / Estilista",
        "empresa": "Barbería Barber Moon",
        "edad_minima": 20,
        "ubicacion": {"lat": -33.4489, "lon": -70.6693},
        "habilidades_requeridas": ["corte_cabello", "atencion_cliente"],
        "sueldo_ofrecido": 650000
    }
]

def obtener_o_crear_usuario():
    """Asigna una ID única a cada dispositivo que entra a la web"""
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())[:8]
    
    uid = session["user_id"]
    if uid not in candidatos_db:
        candidatos_db[uid] = {
            "nombre": f"Usuario #{uid}",
            "edad": 22,
            "expectativa_renta": 550000,
            "habilidades": ["atencion_cliente", "caja"],
            "ubicacion": {"lat": -33.4489, "lon": -70.6693}
        }
    return uid

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

NAV_BAR = """
<nav class="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 flex justify-around py-3 text-xs text-gray-400 z-50">
    <a href="/" class="flex flex-col items-center hover:text-amber-500">
        <span class="text-lg">🏠</span>Inicio
    </a>
    <a href="/candidato/feed" class="flex flex-col items-center hover:text-amber-500">
        <span class="text-lg">🔥</span>Empleos
    </a>
    <a href="/chats" class="flex flex-col items-center hover:text-amber-500">
        <span class="text-lg">💬</span>Chats
    </a>
    <a href="/candidato/perfil" class="flex flex-col items-center hover:text-amber-500">
        <span class="text-lg">👤</span>Perfil
    </a>
    <a href="/empleador" class="flex flex-col items-center hover:text-amber-500">
        <span class="text-lg">🏢</span>Empresa
    </a>
</nav>
"""

HTML_HEAD = """
<head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>PalApp</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
"""

HTML_HOME = f"""
<!DOCTYPE html>
<html lang="es">
{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen pb-20 flex flex-col justify-center items-center px-4">
    <div class="text-center max-w-sm w-full">
        <div class="w-20 h-20 bg-amber-500 rounded-full flex items-center justify-center text-4xl mx-auto mb-4 shadow-lg shadow-amber-500/20">⚡</div>
        <h1 class="text-3xl font-extrabold tracking-tight">PalApp</h1>
        <p class="text-gray-400 text-sm mt-1 mb-2">Conecta candidatos y empleadores</p>
        <p class="text-amber-500 text-xs mb-8 font-mono">Dispositivo ID: {{{{ uid }}}}</p>
        
        <div class="space-y-3">
            <a href="/candidato/feed" class="block w-full py-3.5 px-4 bg-amber-500 hover:bg-amber-600 text-gray-950 font-bold rounded-xl shadow-md transition">🔥 Buscar Empleo (Swipe)</a>
            <a href="/chats" class="block w-full py-3.5 px-4 bg-gray-800 hover:bg-gray-700 font-semibold rounded-xl transition">💬 Mis Conversaciones</a>
            <a href="/candidato/perfil" class="block w-full py-3 px-4 bg-gray-900 border border-gray-800 text-gray-300 font-medium rounded-xl transition">👤 Configurar Mi Perfil</a>
            <a href="/empleador" class="block w-full py-3 px-4 bg-gray-900 border border-gray-800 text-gray-300 font-medium rounded-xl transition">🏢 Modo Empleador</a>
        </div>
    </div>
    {NAV_BAR}
</body>
</html>
"""

HTML_FEED = f"""
<!DOCTYPE html>
<html lang="es">
{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen pb-20 px-4 pt-6">
    <div class="max-w-sm mx-auto">
        <h2 class="text-xl font-bold mb-4 text-center">Ofertas Disponibles</h2>
        <div id="card" class="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl relative min-h-[280px] flex flex-col justify-between">
            <div id="content">Cargando ofertas...</div>
        </div>
        <div id="actions" class="flex justify-center gap-6 mt-6 hidden">
            <button onclick="next(false)" class="w-16 h-16 bg-gray-900 border border-red-500/30 text-red-500 rounded-full text-2xl shadow-lg hover:bg-red-500/10 transition">❌</button>
            <button onclick="next(true)" class="w-16 h-16 bg-amber-500 text-gray-950 rounded-full text-2xl shadow-lg shadow-amber-500/20 hover:bg-amber-400 transition">💚</button>
        </div>
    </div>
    {NAV_BAR}
    <script>
    let items=[], idx=0;
    fetch('/api/ofertas').then(r=>r.json()).then(d=>{{items=d;show();}});
    function show(){{
        let c=document.getElementById('content'), a=document.getElementById('actions');
        if(idx>=items.length){{
            c.innerHTML='<div class="text-center py-10"><p class="text-4xl mb-2">🎉</p><p class="font-bold">¡No hay más ofertas!</p><p class="text-xs text-gray-400 mt-1">Revisa tus chats para dar seguimiento</p></div>';
            a.classList.add('hidden'); return;
        }}
        let o=items[idx]; a.classList.remove('hidden');
        c.innerHTML='<div><div class="flex justify-between items-start mb-2"><span class="bg-amber-500/10 text-amber-500 border border-amber-500/20 text-xs px-2.5 py-1 rounded-full font-bold">'+o.match+'% Match</span><span class="text-xs text-gray-400">CLP $'+o.sueldo_ofrecido.toLocaleString('es-CL')+'</span></div><h3 class="text-lg font-bold text-white mb-1">'+o.titulo+'</h3><p class="text-sm text-gray-400 mb-4">'+o.empresa+'</p><div class="flex flex-wrap gap-1.5 mb-2">'+o.habilidades_requeridas.map(h=>'<span class="bg-gray-800 text-gray-300 text-[10px] px-2 py-0.5 rounded">'+h+'</span>').join('')+'</div></div>';
    }}
    async function next(ok){{
        if(ok){{
            let o=items[idx];
            let r = await fetch('/api/crear-chat', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{job_id: o.id}})
            }});
            let res = await r.json();
            location.href = '/chat/' + o.id;
        }} else {{
            idx++; show();
        }}
    }}
    </script>
</body>
</html>
"""

HTML_CHATS_LIST = f"""
<!DOCTYPE html>
<html lang="es">
{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen pb-20">
    <div class="p-4 border-b border-gray-800 bg-gray-900">
        <h1 class="font-bold text-lg">💬 Mensajes</h1>
        <p class="text-xs text-gray-400">Conversaciones activas con empresas</p>
    </div>
    
    <div id="chats-list" class="divide-y divide-gray-800">
        <p class="p-4 text-xs text-gray-500">Cargando chats...</p>
    </div>
    {NAV_BAR}
    <script>
    async function loadChats(){{
        let r = await fetch('/api/mis-chats');
        let chats = await r.json();
        let cont = document.getElementById('chats-list');
        if(chats.length === 0){{
            cont.innerHTML = '<div class="p-8 text-center text-gray-500 text-xs"><p class="text-2xl mb-2">📭</p>No tienes chats activos.<br>Usa el buscador para dar Me Gusta (💚) a empleos.</div>';
            return;
        }}
        cont.innerHTML = chats.map(c=> `
            <a href="/chat/${{c.job_id}}" class="flex items-center gap-3 p-4 hover:bg-gray-900 transition">
                <div class="w-12 h-12 bg-amber-500/10 border border-amber-500/20 rounded-full flex items-center justify-center font-bold text-amber-500 text-lg">
                    🏢
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex justify-between items-baseline">
                        <h4 class="font-bold text-sm text-white truncate">${{c.titulo_empleo}}</h4>
                        <span class="text-[10px] text-gray-500">${{c.ultima_hora}}</span>
                    </div>
                    <p class="text-xs text-gray-400 truncate">${{c.empresa}}</p>
                    <p class="text-xs text-gray-500 truncate mt-0.5">${{c.ultimo_msg}}</p>
                </div>
            </a>
        `).join('');
    }}
    loadChats();
    </script>
</body>
</html>
"""

HTML_CHAT_ROOM = f"""
<!DOCTYPE html>
<html lang="es">
{HTML_HEAD}
<body class="bg-gray-950 text-white h-screen flex flex-col pb-16">
    <div class="p-4 border-b border-gray-800 bg-gray-900 flex justify-between items-center">
        <div class="flex items-center gap-3">
            <a href="/chats" class="text-amber-500 text-lg font-bold">←</a>
            <div>
                <h1 class="font-bold text-sm leading-tight">{{{{ oferta.titulo }}}}</h1>
                <p class="text-[10px] text-gray-400">{{{{ oferta.empresa }}}}</p>
            </div>
        </div>
    </div>
    
    <div id="msgs" class="flex-1 overflow-y-auto p-4 space-y-3"></div>
    
    <form onsubmit="send(event)" class="p-3 bg-gray-900 border-t border-gray-800 flex gap-2">
        <input id="txt" class="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-amber-500" placeholder="Escribe un mensaje..." required>
        <button type="submit" class="bg-amber-500 text-gray-950 px-4 py-2 rounded-xl font-bold text-sm">Enviar</button>
    </form>
    {NAV_BAR}
    <script>
    const jobId = "{{{{ oferta.id }}}}";
    async function load(){{
        let r = await fetch('/api/chat/' + jobId + '/mensajes');
        let d = await r.json();
        let c = document.getElementById('msgs');
        c.innerHTML = d.map(m=> `
            <div class="flex flex-col ${{m.emisor==='candidato'?'items-end':'items-start'}}">
                <div class="max-w-[80%] rounded-2xl px-4 py-2 text-sm ${{m.emisor==='candidato'?'bg-amber-500 text-gray-950 font-medium rounded-br-none':'bg-gray-800 text-white rounded-bl-none'}}">
                    <p class="text-[9px] opacity-60 mb-0.5">${{m.nombre_emisor}}</p>
                    <p>${{m.texto}}</p>
                </div>
                <span class="text-[9px] text-gray-500 mt-0.5 px-1">${{m.hora}}</span>
            </div>
        `).join('');
        c.scrollTop = c.scrollHeight;
    }}
    async function send(e){{
        e.preventDefault();
        let t = document.getElementById('txt');
        await fetch('/api/chat/' + jobId + '/mensajes', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{texto: t.value}})
        }});
        t.value = ''; load();
    }}
    load(); setInterval(load, 2000);
    </script>
</body>
</html>
"""

HTML_CANDIDATO_PERFIL = f"""
<!DOCTYPE html>
<html lang="es">
{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen pb-20 px-4 pt-6">
    <div class="max-w-sm mx-auto bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl">
        <h2 class="text-lg font-bold mb-1">👤 Mi Perfil Candidato</h2>
        <p class="text-xs text-amber-500 font-mono mb-4">ID Dispositivo: {{{{ uid }}}}</p>
        
        <form onsubmit="save(event)" class="space-y-3 text-xs">
            <div><label class="text-gray-400 block mb-1">Nombre</label><input id="nom" value="{{{{ cand.nombre }}}}" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2.5 text-white"></div>
            <div><label class="text-gray-400 block mb-1">Edad</label><input id="edad" type="number" value="{{{{ cand.edad }}}}" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2.5 text-white"></div>
            <div><label class="text-gray-400 block mb-1">Expectativa Renta (CLP)</label><input id="renta" type="number" value="{{{{ cand.expectativa_renta }}}}" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2.5 text-white"></div>
            <div><label class="text-gray-400 block mb-1">Habilidades (separadas por coma)</label><input id="hab" value="{{{{ cand.habilidades | join(', ') }}}}" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2.5 text-white"></div>
            <button type="submit" class="w-full bg-amber-500 text-gray-950 font-bold py-3 rounded-xl mt-2">Guardar Cambios</button>
        </form>
    </div>
    {NAV_BAR}
    <script>
    async function save(e){{
        e.preventDefault();
        await fetch('/api/perfil-candidato',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{
            nombre:document.getElementById('nom').value, edad:document.getElementById('edad').value,
            expectativa_renta:document.getElementById('renta').value, habilidades:document.getElementById('hab').value
        }})}});
        alert("¡Perfil guardado para tu dispositivo!");
    }}
    </script>
</body>
</html>
"""

HTML_EMPLEADOR = f"""
<!DOCTYPE html>
<html lang="es">
{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen pb-20 px-4 pt-6 space-y-4">
    <div class="max-w-sm mx-auto bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl">
        <h2 class="text-md font-bold mb-3">🏢 Perfil Empresa</h2>
        <form onsubmit="saveE(event)" class="space-y-2 text-xs">
            <input id="e_nom" value="{{{{ emp.nombre_empresa }}}}" placeholder="Nombre Empresa" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
            <input id="e_rut" value="{{{{ emp.rut_empresa }}}}" placeholder="RUT Empresa" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
            <input id="e_con" value="{{{{ emp.contacto }}}}" placeholder="Teléfono" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
            <button type="submit" class="w-full bg-gray-800 text-amber-500 font-bold py-2 rounded-lg border border-gray-700">Actualizar Empresa</button>
        </form>
    </div>

    <div class="max-w-sm mx-auto bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl">
        <h2 class="text-md font-bold mb-3">📢 Publicar Nueva Oferta</h2>
        <form onsubmit="pubO(event)" class="space-y-2 text-xs">
            <input id="o_tit" placeholder="Título del Puesto" required class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
            <input id="o_sue" type="number" placeholder="Sueldo Ofrecido" required class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
            <input id="o_hab" placeholder="Requisitos (ej: caja, atencion_cliente)" required class="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-white">
            <button type="submit" class="w-full bg-emerald-500 text-gray-950 font-bold py-2.5 rounded-lg">Publicar Oferta</button>
        </form>
    </div>
    {NAV_BAR}
    <script>
    async function saveE(e){{
        e.preventDefault();
        await fetch('/api/perfil-empleador',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{
            nombre_empresa:document.getElementById('e_nom').value, rut_empresa:document.getElementById('e_rut').value, contacto:document.getElementById('e_con').value
        }})}});
        alert("Empresa actualizada"); location.reload();
    }}
    async function pubO(e){{
        e.preventDefault();
        await fetch('/api/crear-empleo',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{
            titulo:document.getElementById('o_tit').value, sueldo_ofrecido:document.getElementById('o_sue').value, habilidades:document.getElementById('o_hab').value
        }})}});
        alert("Oferta publicada con éxito"); location.reload();
    }}
    </script>
</body>
</html>
"""

# Rutas Principales
@app.route("/")
def home():
    uid = obtener_o_crear_usuario()
    return render_template_string(HTML_HOME, uid=uid)

@app.route("/candidato/feed")
def candidato_feed():
    obtener_o_crear_usuario()
    return render_template_string(HTML_FEED)

@app.route("/candidato/perfil")
def candidato_perfil():
    uid = obtener_o_crear_usuario()
    cand = candidatos_db[uid]
    return render_template_string(HTML_CANDIDATO_PERFIL, cand=cand, uid=uid)

@app.route("/chats")
def vista_chats():
    obtener_o_crear_usuario()
    return render_template_string(HTML_CHATS_LIST)

@app.route("/chat/<job_id>")
def vista_chat_room(job_id):
    obtener_o_crear_usuario()
    oferta = next((o for o in ofertas if o["id"] == job_id), None)
    if not oferta:
        return "Oferta no encontrada", 404
    return render_template_string(HTML_CHAT_ROOM, oferta=oferta)

@app.route("/empleador")
def vista_empleador():
    return render_template_string(HTML_EMPLEADOR, emp=perfil_empleador)

# APIs
@app.route("/api/ofertas", methods=["GET"])
def get_ofertas():
    uid = obtener_o_crear_usuario()
    cand = candidatos_db[uid]
    res = []
    for o in ofertas:
        item = dict(o)
        item["match"] = calcular_match(cand, o)
        res.append(item)
    res.sort(key=lambda x: x["match"], reverse=True)
    return jsonify(res)

@app.route("/api/crear-chat", methods=["POST"])
def crear_chat():
    uid = obtener_o_crear_usuario()
    data = request.json or {}
    job_id = data.get("job_id")
    chat_key = f"{uid}_{job_id}"
    
    if chat_key not in chats_db:
        oferta = next((o for o in ofertas if o["id"] == job_id), None)
        emp_nombre = oferta["empresa"] if oferta else "Empresa"
        
        # Mensaje automático de bienvenida al hacer match
        chats_db[chat_key] = [
            {
                "emisor": "empleador",
                "nombre_emisor": emp_nombre,
                "texto": f"¡Hola! Vimos que te interesó nuestra oferta para {oferta['titulo'] if oferta else 'el puesto'}. ¿Tienes alguna consulta?",
                "hora": datetime.now().strftime("%H:%M")
            }
        ]
    return jsonify({"status": "ok", "chat_key": chat_key})

@app.route("/api/mis-chats", methods=["GET"])
def mis_chats():
    uid = obtener_o_crear_usuario()
    mis = []
    for chat_key, msgs in chats_db.items():
        if chat_key.startswith(f"{uid}_"):
            job_id = chat_key.split("_", 1)[1]
            oferta = next((o for o in ofertas if o["id"] == job_id), None)
            if oferta and msgs:
                ultimo = msgs[-1]
                mis.append({
                    "job_id": job_id,
                    "titulo_empleo": oferta["titulo"],
                    "empresa": oferta["empresa"],
                    "ultimo_msg": ultimo["te
