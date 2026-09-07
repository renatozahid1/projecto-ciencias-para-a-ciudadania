from flask import Flask, render_template_string, jsonify, request, session, redirect
import math
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = "palapp_secret_key_super_segura_123"

# --- BASE DE DATOS EN MEMORIA ---
users_db = {
    "barbermoon": {
        "pwd": "123", 
        "role": "empleador", 
        "nombre": "Barbería Barber Moon", 
        "descripcion": "Somos una barbería con más de 8 años de trayectoria en el centro de la ciudad. Buscamos el mejor talento en corte tradicional y moderno.",
        "ubicacion": {"lat": -33.4489, "lon": -70.6693, "region": "Región Metropolitana", "ciudad": "Santiago"}, 
        "contacto": "+56912345678",
        "mensaje_bienvenida": "¡Hola! Vi tu perfil en PalApp y nos encantaría agendar una entrevista.",
        "foto": "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=400&h=300&fit=crop"
    },
    "juanp": {
        "pwd": "123", 
        "role": "candidato", 
        "nombre": "Juan Pérez", 
        "descripcion": "Barbero profesional apasionado por el corte urbano, degradados y perfilado de barba. 3 años de experiencia en barberías concurridas.",
        "edad": 24,
        "ubicacion": {"lat": -33.4489, "lon": -70.6693, "region": "Región Metropolitana", "ciudad": "Santiago"}, 
        "expectativa_renta": 600000,
        "habilidades": ["corte_cabello", "atencion_cliente", "barberia"],
        "foto": "https://ui-avatars.com/api/?name=Juan+Perez&background=1f2937&color=fff"
    }
}

ofertas_db = [
    {
        "id": "job_102", 
        "empleador_id": "barbermoon", 
        "titulo": "Barbero / Estilista Senior",
        "empresa": "Barbería Barber Moon", 
        "descripcion": "Se busca barbero con experiencia comprobable en degradados, perfilado de barba y excelente trato con el cliente.",
        "edad_minima": 20,
        "ubicacion": {"lat": -33.4489, "lon": -70.6693, "region": "Región Metropolitana", "ciudad": "Santiago"},
        "habilidades_requeridas": ["corte_cabello", "atencion_cliente"],
        "sueldo_ofrecido": 650000,
        "foto": "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=400&h=300&fit=crop"
    }
]

# Registros de Interacción
swipes_db = {}
chats_db = {}

# --- LÓGICA DE MATCH ---
def calcular_match(cand, emp_oferta):
    if cand.get("edad", 0) < emp_oferta.get("edad_minima", 18):
        return 0.0
    
    cand_skills = set(cand.get("habilidades", []))
    req_skills = set(emp_oferta.get("habilidades_requeridas", []))
    s_skills = len(cand_skills.intersection(req_skills)) / len(req_skills) if req_skills else 1.0
    
    cand_loc = cand.get("ubicacion", {"lat": -33.4489, "lon": -70.6693})
    emp_loc = emp_oferta.get("ubicacion", {"lat": -33.4489, "lon": -70.6693})
    
    dlat = math.radians(emp_loc.get("lat", -33.4489) - cand_loc.get("lat", -33.4489))
    dlon = math.radians(emp_loc.get("lon", -70.6693) - cand_loc.get("lon", -70.6693))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(cand_loc.get("lat", -33.4489))) * math.cos(math.radians(emp_loc.get("lat", -33.4489))) * math.sin(dlon/2)**2
    dist_km = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    s_dist = math.exp(-0.08 * dist_km)
    
    sueldo_emp = emp_oferta.get("sueldo_ofrecido", 0)
    exp_cand = cand.get("expectativa_renta", 1) or 1
    s_sal = 1.0 if sueldo_emp >= exp_cand else (sueldo_emp / exp_cand)
    
    return round((0.45 * s_skills + 0.35 * s_dist + 0.20 * s_sal) * 100, 1)

def check_match_mutuo(cand_id, emp_id, job_id=None):
    # Verifica si el candidato dio like a alguna oferta del empleador o a una en específico
    mis_ofertas_ids = [o["id"] for o in ofertas_db if o["empleador_id"] == emp_id]
    c_likes_e = any(swipes_db.get((cand_id, j_id)) == "like" for j_id in mis_ofertas_ids)
    e_likes_c = swipes_db.get((emp_id, cand_id)) == "like"
    
    if c_likes_e and e_likes_c:
        chat_key = f"{cand_id}_{emp_id}"
        if chat_key not in chats_db:
            empleador = users_db.get(emp_id, {})
            msg_bienvenida = empleador.get("mensaje_bienvenida", "🎉 ¡Es un Match Mutuo! Ya pueden conversar.")
            chats_db[chat_key] = [{
                "emisor": emp_id, 
                "nombre_emisor": empleador.get("nombre", "Empleador"),
                "texto": msg_bienvenida,
                "hora": datetime.now().strftime("%H:%M")
            }]
        return True
    return False

# --- COMPONENTES FRONTEND ---
NAV_BAR = """
<nav class="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 flex justify-around py-3 text-xs text-gray-400 z-50">
    <a href="/feed" class="flex flex-col items-center hover:text-amber-500"><span class="text-xl">🔥</span>Swipe</a>
    <a href="/chats" class="flex flex-col items-center hover:text-amber-500"><span class="text-xl">💬</span>Chats</a>
    <a href="/perfil" class="flex flex-col items-center hover:text-amber-500"><span class="text-xl">👤</span>Perfil</a>
</nav>
"""

HTML_HEAD = """
<head>
    <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
    <meta name="theme-color" content="#f59e0b">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/manifest.json">
    <title>PalApp</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .card-drag { transition: transform 0.2s ease, opacity 0.2s ease; cursor: grab; }
        .card-drag:active { cursor: grabbing; transition: none; }
        .match-overlay { display: none; background: rgba(0,0,0,0.92); z-index: 100; }
        .modal-bg { display: none; background: rgba(0,0,0,0.85); z-index: 90; }
    </style>
</head>
"""

HTML_AUTH = f"""
<!DOCTYPE html><html lang="es">{HTML_HEAD}
<body class="bg-gray-950 text-white min-h-screen flex flex-col justify-center items-center px-4 py-8">
    <div class="w-full max-w-sm text-center mb-6">
        <div class="w-16 h-16 bg-amber-500 rounded-full flex items-center justify-center text-3xl mx-auto mb-3 shadow-lg shadow-amber-500/20">⚡</div>
        <h1 class="text-3xl font-extrabold tracking-tight">PalApp</h1>
        <p class="text-gray-400 text-xs mt-1">Empleos y Talento al instante</p>
    </div>

    <div class="w-full max-w-sm bg-gray-900 p-6 rounded-2xl border border-gray-800 shadow-xl">
        <div class="flex border-b border-gray-800 mb-5">
            <button id="tab-login-btn" onclick="switchTab('login')" class="flex-1 py-2 text-center text-sm font-bold border-b-2 border-amber-500 text-amber-500">Ingresar</button>
            <button id="tab-register-btn" onclick="switchTab('register')" class="flex-1 py-2 text-center text-sm font-bold border-b-2 border-transparent text-gray-400 hover:text-white">Registrarse</button>
        </div>

        <!-- FORMULARIO LOGIN -->
        <form id="loginForm" onsubmit="handleLogin(event)" class="space-y-4">
            <input id="login-user" placeholder="Usuario" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:border-amber-500 outline-none">
            <input id="login-pwd" type="password" placeholder="Contraseña" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:border-amber-500 outline-none">
            <button type="submit" class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-gray-950 font-bold rounded-xl transition">Iniciar Sesión</button>
        </form>

        <!-- FORMULARIO REGISTRO -->
        <form id="registerForm" onsubmit="handleRegister(event)" class="space-y-3 hidden">
            <div class="flex gap-2">
                <label class="flex-1 text-center py-2 bg-gray-800 border border-gray-700 rounded-xl cursor-pointer text-xs font-bold text-gray-300 has-[:checked]:border-amber-500 has-[:checked]:text-amber-500">
                    <input type="radio" name="role" value="candidato" checked class="hidden" onchange="toggleRoleFields()"> Candidato
                </label>
                <label class="flex-1 text-center py-2 bg-gray-800 border border-gray-700 rounded-xl cursor-pointer text-xs font-bold text-gray-300 has-[:checked]:border-amber-500 has-[:checked]:text-amber-500">
                    <input type="radio" name="role" value="empleador" class="hidden" onchange="toggleRoleFields()"> Empleador
                </label>
            </div>

            <input id="reg-user" placeholder="Usuario" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
            <input id="reg-nombre" placeholder="Nombre completo o Empresa" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
            <input id="reg-pwd" type="password" placeholder="Contraseña" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
            
            <textarea id="reg-desc" placeholder="Descripción / Biografía breve" rows="2" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none"></textarea>

            <div class="space-y-1">
                <label class="text-[10px] text-gray-400 font-bold block">Foto de perfil (Subir archivo o pegar enlace)</label>
                <input type="file" accept="image/*" onchange="convertFileToBase64(this, 'reg-foto-val')" class="w-full text-xs text-gray-400 bg-gray-800 border border-gray-700 rounded-xl px-3 py-1.5">
                <input id="reg-foto-val" placeholder="O pega enlace de imagen (URL)" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-xs focus:border-amber-500 outline-none">
            </div>

            <div class="grid grid-cols-2 gap-2">
                <input id="reg-region" placeholder="Región" required class="bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                <input id="reg-ciudad" placeholder="Ciudad" required class="bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
            </div>

            <!-- Campos dinámicos Candidato -->
            <div id="cand-fields" class="space-y-2">
                <div class="grid grid-cols-2 gap-2">
                    <input id="reg-edad" type="number" placeholder="Edad" class="bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                    <input id="reg-renta" type="number" placeholder="Expectativa Renta ($)" class="bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                </div>
                <input id="reg-skills" placeholder="Habilidades (ej: barberia, atencion)" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
            </div>

            <!-- Campos dinámicos Empleador -->
            <div id="emp-fields" class="space-y-2 hidden">
                <input id="reg-contacto" placeholder="Teléfono de contacto" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                <input id="reg-job-title" placeholder="Título de tu 1° Oferta (ej: Barbero)" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                <input id="reg-job-sueldo" type="number" placeholder="Sueldo ofrecido ($)" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
            </div>

            <button type="submit" class="w-full py-3 bg-amber-500 hover:bg-amber-600 text-gray-950 font-bold rounded-xl transition mt-2">Crear Cuenta</button>
        </form>
    </div>

    <script>
    function convertFileToBase64(fileInput, targetId) {{
        const file = fileInput.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(e) {{
            document.getElementById(targetId).value = e.target.result;
        }};
        reader.readAsDataURL(file);
    }}

    function switchTab(tab) {{
        if(tab === 'login') {{
            document.getElementById('loginForm').classList.remove('hidden');
            document.getElementById('registerForm').classList.add('hidden');
            document.getElementById('tab-login-btn').className = "flex-1 py-2 text-center text-sm font-bold border-b-2 border-amber-500 text-amber-500";
            document.getElementById('tab-register-btn').className = "flex-1 py-2 text-center text-sm font-bold border-b-2 border-transparent text-gray-400";
        }} else {{
            document.getElementById('loginForm').classList.add('hidden');
            document.getElementById('registerForm').classList.remove('hidden');
            document.getElementById('tab-register-btn').className = "flex-1 py-2 text-center text-sm font-bold border-b-2 border-amber-500 text-amber-500";
            document.getElementById('tab-login-btn').className = "flex-1 py-2 text-center text-sm font-bold border-b-2 border-transparent text-gray-400";
        }}
    }}

    function toggleRoleFields() {{
        let role = document.querySelector('input[name="role"]:checked').value;
        if(role === 'candidato') {{
            document.getElementById('cand-fields').classList.remove('hidden');
            document.getElementById('emp-fields').classList.add('hidden');
        }} else {{
            document.getElementById('cand-fields').classList.add('hidden');
            document.getElementById('emp-fields').classList.remove('hidden');
        }}
    }}

    async function handleLogin(e) {{
        e.preventDefault();
        let r = await fetch('/api/login', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{user: document.getElementById('login-user').value, pwd: document.getElementById('login-pwd').value}})
        }});
        let res = await r.json();
        if(res.status === 'ok') location.href = '/feed'; else alert(res.msg);
    }}

    async function handleRegister(e) {{
        e.preventDefault();
        let role = document.querySelector('input[name="role"]:checked').value;
        let payload = {{
            user: document.getElementById('reg-user').value,
            pwd: document.getElementById('reg-pwd').value,
            nombre: document.getElementById('reg-nombre').value,
            descripcion: document.getElementById('reg-desc').value,
            foto: document.getElementById('reg-foto-val').value,
            role: role,
            region: document.getElementById('reg-region').value,
            ciudad: document.getElementById('reg-ciudad').value,
            edad: document.getElementById('reg-edad').value,
            expectativa_renta: document.getElementById('reg-renta').value,
            habilidades: document.getElementById('reg-skills').value,
            contacto: document.getElementById('reg-contacto').value,
            titulo_oferta: document.getElementById('reg-job-title').value,
            sueldo_ofrecido: document.getElementById('reg-job-sueldo').value
        }};

        let r = await fetch('/api/register', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify(payload)
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
        <span class="bg-amber-500/10 border border-amber-500/30 text-amber-500 px-3 py-1 rounded-full text-xs font-bold capitalize">{{{{ user.role }}}}</span>
    </div>

    <div class="max-w-sm mx-auto relative h-[65vh]" id="card-container"></div>

    <div class="max-w-sm mx-auto flex justify-center gap-6 mt-4 z-10 relative items-center">
        <button onclick="action('pass')" class="w-16 h-16 bg-gray-900 border-2 border-red-500/50 text-red-500 rounded-full text-3xl shadow-lg hover:bg-red-500/20 transition flex items-center justify-center">❌</button>
        <button onclick="openProfileModal()" class="w-12 h-12 bg-gray-800 border border-gray-700 text-amber-400 rounded-full text-xl shadow-md hover:bg-gray-700 transition flex items-center justify-center">👁️</button>
        <button onclick="action('like')" class="w-16 h-16 bg-amber-500 text-gray-950 rounded-full text-3xl shadow-lg shadow-amber-500/20 hover:bg-amber-400 transition flex items-center justify-center">💚</button>
    </div>

    <!-- Modal Ver Perfil Completo -->
    <div id="profile-modal" class="modal-bg fixed inset-0 flex items-center justify-center p-4">
        <div class="bg-gray-900 border border-gray-800 w-full max-w-sm rounded-2xl p-5 relative max-h-[85vh] overflow-y-auto">
            <button onclick="closeProfileModal()" class="absolute top-4 right-4 text-gray-400 hover:text-white text-xl font-bold">✕</button>
            <div class="text-center mb-4">
                <img id="m-foto" src="" class="w-24 h-24 rounded-full border-4 border-amber-500 mx-auto mb-2 object-cover">
                <h3 id="m-nombre" class="text-xl font-bold"></h3>
                <p id="m-subtitulo" class="text-xs text-amber-400 font-medium"></p>
                <p id="m-ubicacion" class="text-xs text-gray-400 mt-0.5"></p>
            </div>
            
            <div class="space-y-3 text-sm border-t border-gray-800 pt-3">
                <div>
                    <h4 class="text-xs font-bold text-gray-400 uppercase">Acerca de / Descripción</h4>
                    <p id="m-desc" class="text-gray-200 mt-1 leading-relaxed text-xs bg-gray-950 p-3 rounded-xl border border-gray-800"></p>
                </div>
                <div>
                    <h4 class="text-xs font-bold text-gray-400 uppercase mb-1">Habilidades / Requisitos</h4>
                    <div id="m-tags" class="flex flex-wrap gap-1"></div>
                </div>
            </div>
        </div>
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
            container.innerHTML = '<div class="h-full bg-gray-900 rounded-2xl border border-gray-800 flex flex-col items-center justify-center text-center p-6"><span class="text-5xl mb-4">📭</span><h3 class="font-bold text-lg">No hay más publicaciones u ofertas por ahora</h3></div>';
            currentItem = null;
            return;
        }}

        currentItem = queue[0];
        const tags = (currentItem.habilidades || currentItem.habilidades_requeridas || []).map(h => `<span class="bg-gray-800/80 backdrop-blur-sm text-gray-200 text-[11px] px-2.5 py-1 rounded-md border border-gray-700">#${{h}}</span>`).join(' ');
        const sueldo_texto = currentItem.sueldo_ofrecido ? `$${{currentItem.sueldo_ofrecido.toLocaleString('es-CL')}}` : (currentItem.expectativa_renta ? `$${{currentItem.expectativa_renta.toLocaleString('es-CL')}} (Exp)` : '');
        const loc_texto = currentItem.ubicacion ? `${{currentItem.ubicacion.ciudad || ''}}, ${{currentItem.ubicacion.region || ''}}` : '';
        const es_solicitud = currentItem.postulado_a ? `<div class="bg-amber-500 text-gray-950 text-[11px] font-extrabold px-3 py-1 rounded-full mb-2 inline-block shadow-md">⚡ Postuló a tu oferta: ${{currentItem.postulado_a}}</div>` : '';

        container.innerHTML = `
            <div id="swipe-card" class="card-drag absolute inset-0 bg-gray-900 border border-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col bg-cover bg-center" style="background-image: linear-gradient(to top, rgba(3,7,18,1) 0%, rgba(3,7,18,0.7) 40%, rgba(3,7,18,0) 100%), url('${{currentItem.foto}}')">
                <div class="mt-auto p-5 relative z-10">
                    ${{es_solicitud}}
                    <div class="flex justify-between items-end mb-2">
                        <span class="bg-amber-500 text-gray-950 text-xs px-3 py-1 rounded-full font-extrabold shadow-lg">${{currentItem.match_score}}% Match</span>
                    </div>
                    <h2 class="text-2xl font-extrabold text-white mb-1">${{currentItem.titulo || currentItem.nombre}} <span class="text-lg font-normal text-gray-300">${{currentItem.edad ? currentItem.edad + ' años' : ''}}</span></h2>
                    <p class="text-amber-400 font-medium text-sm mb-1">${{currentItem.empresa || currentItem.nombre}} | ${{sueldo_texto}}</p>
                    <p class="text-gray-300 text-xs mb-2 line-clamp-2">${{currentItem.descripcion || 'Sin descripción.'}}</p>
                    <p class="text-gray-400 text-xs mb-3">📍 ${{loc_texto}}</p>
                    <div class="flex flex-wrap gap-1.5">${{tags}}</div>
                </div>
            </div>
        `;
        
        cardEl = document.getElementById('swipe-card');
        setupGestures(cardEl);
    }}

    function openProfileModal() {{
        if(!currentItem) return;
        document.getElementById('m-foto').src = currentItem.foto;
        document.getElementById('m-nombre').innerText = currentItem.titulo || currentItem.nombre;
        document.getElementById('m-subtitulo').innerText = (currentItem.empresa ? currentItem.empresa + ' | ' : '') + (currentItem.sueldo_ofrecido ? '$' + currentItem.sueldo_ofrecido.toLocaleString('es-CL') : (currentItem.expectativa_renta ? '$' + currentItem.expectativa_renta.toLocaleString('es-CL') : ''));
        document.getElementById('m-ubicacion').innerText = currentItem.ubicacion ? `📍 ${{currentItem.ubicacion.ciudad}}, ${{currentItem.ubicacion.region}}` : '';
        document.getElementById('m-desc').innerText = currentItem.descripcion || 'Sin descripción agregada.';
        
        const tags = (currentItem.habilidades || currentItem.habilidades_requeridas || []).map(h => `<span class="bg-gray-800 text-amber-400 text-xs px-2.5 py-1 rounded-md border border-gray-700">#${{h}}</span>`).join(' ');
        document.getElementById('m-tags').innerHTML = tags || '<span class="text-gray-500 text-xs">Sin habilidades listadas</span>';
        
        document.getElementById('profile-modal').style.display = 'flex';
    }}

    function closeProfileModal() {{
        document.getElementById('profile-modal').style.display = 'none';
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
        closeProfileModal();
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

# --- RUTAS DE AUTENTICACIÓN Y FEED ---
@app.route("/")
def index():
    if "user_id" in session and session["user_id"] in users_db: 
        return redirect("/feed")
    return render_template_string(HTML_AUTH)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    u, p = data.get("user", "").strip().lower(), data.get("pwd", "").strip()
    if u in users_db and users_db[u]["pwd"] == p:
        session["user_id"] = u
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "msg": "Usuario o contraseña incorrectos"}), 401

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    u = data.get("user", "").strip().lower()
    p = data.get("pwd", "").strip()
    role = data.get("role", "candidato")
    nombre = data.get("nombre", u).strip()
    region = data.get("region", "Región Metropolitana").strip()
    ciudad = data.get("ciudad", "Santiago").strip()
    foto = data.get("foto") or f"https://ui-avatars.com/api/?name={nombre.replace(' ', '+')}&background=f59e0b&color=fff"

    if not u or not p:
        return jsonify({"status": "error", "msg": "Complete usuario y contraseña"}), 400
    if u in users_db:
        return jsonify({"status": "error", "msg": "El usuario ya se encuentra registrado"}), 400

    users_db[u] = {
        "pwd": p, "role": role, "nombre": nombre,
        "descripcion": data.get("descripcion", ""),
        "ubicacion": {"lat": -33.4489, "lon": -70.6693, "region": region, "ciudad": ciudad},
        "foto": foto,
        "edad": int(data.get("edad") or 22) if role == "candidato" else None,
        "expectativa_renta": int(data.get("expectativa_renta") or 500000) if role == "candidato" else None,
        "habilidades": [h.strip() for h in data.get("habilidades", "").split(",") if h.strip()] if role == "candidato" else [],
        "contacto": data.get("contacto", "") if role == "empleador" else None,
        "mensaje_bienvenida": "¡Hola! Gracias por conectar con nosotros." if role == "empleador" else None
    }

    if role == "empleador":
        ofertas_db.append({
            "id": f"job_{uuid.uuid4().hex[:6]}",
            "empleador_id": u,
            "titulo": data.get("titulo_oferta") or "Puesto Vacante",
            "empresa": nombre,
            "descripcion": data.get("descripcion", "Únete a nuestro equipo de trabajo."),
            "edad_minima": 18,
            "ubicacion": {"lat": -33.4489, "lon": -70.6693, "region": region, "ciudad": ciudad},
            "habilidades_requeridas": ["atencion_cliente"],
            "sueldo_ofrecido": int(data.get("sueldo_ofrecido") or 600000),
            "foto": foto
        })

    session["user_id"] = u
    return jsonify({"status": "ok"})

@app.route("/feed")
def vista_feed():
    u = session.get("user_id")
    if not u or u not in users_db: return redirect("/")
    return render_template_string(HTML_FEED, user=users_db[u])

@app.route("/api/feed", methods=["GET"])
def get_feed():
    u = session.get("user_id")
    if not u or u not in users_db: return jsonify([])
    user = users_db[u]
    res = []
    
    if user["role"] == "candidato":
        for o in ofertas_db:
            if (u, o["id"]) not in swipes_db:
                item = dict(o)
                item["match_score"] = calcular_match(user, o)
                res.append(item)
    else:
        mis_ofertas = [o for o in ofertas_db if o["empleador_id"] == u]
        oferta_base = mis_ofertas[0] if mis_ofertas else {"edad_minima": 18, "habilidades_requeridas": [], "sueldo_ofrecido": 0}

        for cand_id, cand_data in users_db.items():
            if cand_data.get("role") == "candidato" and (u, cand_id) not in swipes_db:
                item = dict(cand_data)
                item["id"] = cand_id
                item["match_score"] = calcular_match(cand_data, oferta_base)
                
                # Buscar si el candidato postuló a alguna de las ofertas de esta empresa
                postulado_job = None
                for o in mis_ofertas:
                    if swipes_db.get((cand_id, o["id"])) == "like":
                        postulado_job = o["titulo"]
                        break
                item["postulado_a"] = postulado_job
                
                res.append(item)
                
    res.sort(key=lambda x: (1 if x.get("postulado_a") else 0, x["match_score"]), reverse=True)
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
        
        # Obtener ID del empleador si la oferta fue el target
        if user_role == "candidato":
            for o in ofertas_db:
                if o["id"] == target:
                    emp_id = o["empleador_id"]
                    break
                    
        is_match = check_match_mutuo(cand_id, emp_id)

    return jsonify({"status": "ok", "is_match": is_match})

# --- SISTEMA DE CHAT ---
@app.route("/chats")
def vista_chats():
    u = session.get("user_id")
    if not u or u not in users_db: return redirect("/")
    
    mis_chats = []
    for chat_key in chats_db:
        parts = chat_key.split("_")
        if u in parts:
            otro_id = parts[0] if parts[1] == u else parts[1]
            if otro_id in users_db:
                ultimo_msg = chats_db[chat_key][-1]["texto"] if chats_db[chat_key] else "¡Nuevo match!"
                mis_chats.append({"id": otro_id, "nombre": users_db[otro_id]["nombre"], "foto": users_db[otro_id]["foto"], "ultimo_msg": ultimo_msg})
            
    html = f"""<!DOCTYPE html><html lang="es">{HTML_HEAD}
    <body class="bg-gray-950 text-white min-h-screen p-4 pb-20">
        <h1 class="text-2xl font-bold mb-4">Mensajes</h1>
        <div class="space-y-3">
            {''.join([f'<a href="/chat/{c["id"]}" class="flex items-center bg-gray-900 p-3 rounded-xl border border-gray-800 hover:border-amber-500 transition"><img src="{c["foto"]}" class="w-12 h-12 rounded-full object-cover border border-amber-500 mr-3"><div class="flex-1 overflow-hidden"><h3 class="font-bold text-sm">{c["nombre"]}</h3><p class="text-xs text-gray-400 truncate">{c["ultimo_msg"]}</p></div></a>' for c in mis_chats])}
            { '<p class="text-gray-500 text-center py-10">No tienes conversaciones activas. ¡Desliza en el feed para encontrar matches!</p>' if not mis_chats else '' }
        </div>
        {NAV_BAR}
    </body></html>"""
    return render_template_string(html)

@app.route("/chat/<target_id>")
def chat_room(target_id):
    u = session.get("user_id")
    if not u or u not in users_db or target_id not in users_db: return redirect("/")
    
    otro_user = users_db[target_id]
    html = f"""<!DOCTYPE html><html lang="es">{HTML_HEAD}
    <body class="bg-gray-950 text-white min-h-screen flex flex-col">
        <div class="bg-gray-900 p-3 flex items-center justify-between border-b border-gray-800 sticky top-0 z-50">
            <div class="flex items-center">
                <button onclick="location.href='/chats'" class="mr-3 text-xl hover:text-amber-500">⬅</button>
                <img src="{otro_user['foto']}" class="w-10 h-10 rounded-full mr-3 object-cover border border-amber-500">
                <div>
                    <h2 class="font-bold text-sm">{otro_user['nombre']}</h2>
                    <span class="text-[10px] text-green-400">● En línea</span>
                </div>
            </div>
            <button onclick="openChatProfile()" class="text-xs bg-gray-800 border border-gray-700 text-amber-400 px-3 py-1.5 rounded-lg hover:bg-gray-700 font-bold">👁️ Ver Perfil</button>
        </div>
        <div id="chat-box" class="flex-1 p-4 overflow-y-auto pb-24 space-y-3"></div>

        <!-- Modal Ver Perfil desde Chat -->
        <div id="chat-profile-modal" class="modal-bg fixed inset-0 flex items-center justify-center p-4">
            <div class="bg-gray-900 border border-gray-800 w-full max-w-sm rounded-2xl p-5 relative max-h-[85vh] overflow-y-auto">
                <button onclick="closeChatProfile()" class="absolute top-4 right-4 text-gray-400 hover:text-white text-xl font-bold">✕</button>
                <div class="text-center mb-4">
                    <img src="{otro_user['foto']}" class="w-24 h-24 rounded-full border-4 border-amber-500 mx-auto mb-2 object-cover">
                    <h3 class="text-xl font-bold">{otro_user['nombre']}</h3>
                    <p class="text-xs text-amber-400 font-medium">{otro_user.get('contacto', '')}</p>
                    <p class="text-xs text-gray-400 mt-0.5">📍 {otro_user.get('ubicacion', {}).get('ciudad', '')}, {otro_user.get('ubicacion', {}).get('region', '')}</p>
                </div>
                <div class="space-y-3 text-sm border-t border-gray-800 pt-3">
                    <div>
                        <h4 class="text-xs font-bold text-gray-400 uppercase">Acerca de / Descripción</h4>
                        <p class="text-gray-200 mt-1 leading-relaxed text-xs bg-gray-950 p-3 rounded-xl border border-gray-800">{otro_user.get('descripcion', 'Sin descripción.')}</p>
                    </div>
                </div>
            </div>
        </div>
        
        <form onsubmit="sendMessage(event)" class="p-3 bg-gray-900 fixed bottom-0 left-0 right-0 border-t border-gray-800 flex gap-2">
            <input id="msg-input" type="text" placeholder="Escribe un mensaje..." class="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-amber-500 text-white">
            <button type="submit" class="bg-amber-500 text-gray-950 font-bold px-4 py-2 rounded-xl hover:bg-amber-400">Enviar</button>
        </form>
        
        <script>
            const targetId = "{target_id}";
            const myId = "{u}";

            function openChatProfile() {{ document.getElementById('chat-profile-modal').style.display = 'flex'; }}
            function closeChatProfile() {{ document.getElementById('chat-profile-modal').style.display = 'none'; }}
            
            async function loadChat() {{
                let r = await fetch('/api/chat/' + targetId);
                let msgs = await r.json();
                let html = msgs.map(m => `
                    <div class="flex ${{m.emisor === myId ? 'justify-end' : 'justify-start'}}">
                        <div class="max-w-[78%] rounded-2xl px-4 py-2 text-sm ${{m.emisor === myId ? 'bg-amber-500 text-gray-950 font-medium rounded-br-none' : 'bg-gray-800 text-white rounded-bl-none border border-gray-700'}}">
                            <p>${{m.texto}}</p>
                            <span class="text-[9px] opacity-70 block text-right mt-1">${{m.hora}}</span>
                        </div>
                    </div>
                `).join('');
                let box = document.getElementById('chat-box');
                box.innerHTML = html;
            }}
            
            async function sendMessage(e) {{
                e.preventDefault();
                let input = document.getElementById('msg-input');
                let text = input.value.trim();
                if(!text) return;
                input.value = '';
                
                await fetch('/api/chat/' + targetId, {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{texto: text}})
                }});
                loadChat();
                setTimeout(() => document.getElementById('chat-box').scrollTo(0, 9999), 100);
            }}
            
            setInterval(loadChat, 2000);
            loadChat();
            setTimeout(() => document.getElementById('chat-box').scrollTo(0, 9999), 200);
        </script>
    </body></html>"""
    return render_template_string(html)

@app.route("/api/chat/<target_id>", methods=["GET", "POST"])
def api_chat(target_id):
    u = session.get("user_id")
    if not u: return jsonify([])
    
    chat_key = f"{u}_{target_id}" if f"{u}_{target_id}" in chats_db else f"{target_id}_{u}"
    
    if request.method == "POST":
        if chat_key not in chats_db: chats_db[chat_key] = []
        chats_db[chat_key].append({
            "emisor": u,
            "texto": request.json.get("texto"),
            "hora": datetime.now().strftime("%H:%M")
        })
        return jsonify({"status": "ok"})
    
    return jsonify(chats_db.get(chat_key, []))

# --- PERFIL Y GESTIÓN DE OFERTAS ---
@app.route("/perfil")
def vista_perfil():
    u = session.get("user_id")
    if not u or u not in users_db: return redirect("/")
    
    user = users_db[u]
    loc = user.get("ubicacion", {})
    region_val = loc.get("region", "")
    ciudad_val = loc.get("ciudad", "")
    
    mis_ofertas = [o for o in ofertas_db if o["empleador_id"] == u]

    html = f"""<!DOCTYPE html><html lang="es">{HTML_HEAD}
    <body class="bg-gray-950 text-white min-h-screen p-4 pb-24">
        <div class="max-w-sm mx-auto">
            <div class="flex items-center justify-between mb-6">
                <h1 class="text-2xl font-bold">👤 Mi Perfil</h1>
                <a href="/logout" class="text-xs bg-red-500/10 border border-red-500/30 text-red-500 px-3 py-1.5 rounded-lg hover:bg-red-500/20 font-bold">Cerrar Sesión</a>
            </div>

            <form onsubmit="saveProfile(event)" class="space-y-4 bg-gray-900 p-5 rounded-2xl border border-gray-800 mb-6">
                <div class="text-center mb-4">
                    <img id="avatar-preview" src="{user.get('foto', '')}" class="w-24 h-24 rounded-full border-4 border-amber-500 mx-auto mb-2 object-cover">
                    <span class="text-xs text-amber-500 font-bold uppercase tracking-wider">{user['role']}</span>
                </div>

                <div>
                    <label class="text-xs text-gray-400 font-bold">Nombre Completo / Empresa</label>
                    <input id="edit-nombre" value="{user.get('nombre', '')}" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">
                </div>

                <div>
                    <label class="text-xs text-gray-400 font-bold">Descripción / Biografía</label>
                    <textarea id="edit-desc" rows="2" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">{user.get('descripcion', '')}</textarea>
                </div>

                <div class="space-y-1">
                    <label class="text-xs text-gray-400 font-bold">Cambiar Foto de Perfil</label>
                    <input type="file" accept="image/*" onchange="convertFileToBase64(this, 'edit-foto', 'avatar-preview')" class="w-full text-xs text-gray-400 bg-gray-800 border border-gray-700 rounded-xl px-3 py-1.5">
                    <input id="edit-foto" value="{user.get('foto', '')}" onchange="document.getElementById('avatar-preview').src=this.value" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-xs mt-1 focus:border-amber-500 outline-none">
                </div>

                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="text-xs text-gray-400 font-bold">Región</label>
                        <input id="edit-region" value="{region_val}" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-gray-400 font-bold">Ciudad</label>
                        <input id="edit-ciudad" value="{ciudad_val}" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">
                    </div>
                </div>

                {"<!-- CAMPOS EDITABLES CANDIDATO -->" if user["role"] == "candidato" else ""}
                <div class="{'space-y-4' if user['role'] == 'candidato' else 'hidden'}">
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="text-xs text-gray-400 font-bold">Edad</label>
                            <input id="edit-edad" type="number" value="{user.get('edad', '')}" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">
                        </div>
                        <div>
                            <label class="text-xs text-gray-400 font-bold">Expectativa Renta ($)</label>
                            <input id="edit-renta" type="number" value="{user.get('expectativa_renta', '')}" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">
                        </div>
                    </div>
                    <div>
                        <label class="text-xs text-gray-400 font-bold">Habilidades (separadas por coma)</label>
                        <input id="edit-skills" value="{', '.join(user.get('habilidades', []))}" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">
                    </div>
                </div>

                {"<!-- CAMPOS EDITABLES EMPLEADOR -->" if user["role"] == "empleador" else ""}
                <div class="{'space-y-4' if user['role'] == 'empleador' else 'hidden'}">
                    <div>
                        <label class="text-xs text-gray-400 font-bold">Contacto Telefónico</label>
                        <input id="edit-contacto" value="{user.get('contacto', '')}" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm mt-1 focus:border-amber-500 outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-amber-500 font-bold">Mensaje de Bienvenida Automático (Match)</label>
                        <textarea id="edit-welcome" class="w-full bg-gray-800 border border-gray-700 rounded-xl p-3 text-sm mt-1 focus:border-amber-500 outline-none" rows="2">{user.get('mensaje_bienvenida', '')}</textarea>
                    </div>
                </div>

                <button type="submit" class="w-full py-3 bg-amber-500 text-gray-950 font-bold rounded-xl hover:bg-amber-400 transition mt-4">Guardar Cambios</button>
                <p id="save-status" class="text-green-400 text-xs text-center hidden font-bold">¡Perfil actualizado correctamente!</p>
            </form>

            <!-- SECCIÓN PUBLICACIONES DE TRABAJO (SÓLO EMPLEADORES) -->
            <div class="{'space-y-4' if user['role'] == 'empleador' else 'hidden'}">
                <div class="flex justify-between items-center mb-2">
                    <h2 class="text-lg font-bold">💼 Mis Ofertas de Trabajo</h2>
                    <button onclick="toggleNewJobForm()" class="text-xs bg-amber-500 text-gray-950 px-3 py-1.5 rounded-lg font-bold hover:bg-amber-400">+ Nueva Oferta</button>
                </div>

                <!-- FORMULARIO CREAR NUEVA OFERTA -->
                <form id="new-job-form" onsubmit="createNewJob(event)" class="bg-gray-900 p-4 rounded-2xl border border-gray-800 space-y-3 hidden">
                    <h3 class="text-sm font-bold text-amber-500">Crear Nueva Oferta de Trabajo</h3>
                    <input id="job-title" placeholder="Título del puesto (ej: Barbera/o)" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                    <textarea id="job-desc" placeholder="Descripción del empleo y funciones" rows="2" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none"></textarea>
                    <input id="job-sueldo" type="number" placeholder="Sueldo ofrecido ($)" required class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                    <input id="job-skills" placeholder="Habilidades requeridas (separadas por coma)" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm focus:border-amber-500 outline-none">
                    
                    <div class="space-y-1">
                        <label class="text-[10px] text-gray-400 font-bold">Foto del Puesto / Local</label>
                        <input type="file" accept="image/*" onchange="convertFileToBase64(this, 'job-foto-val')" class="w-full text-xs text-gray-400 bg-gray-800 border border-gray-700 rounded-xl px-3 py-1.5">
                        <input id="job-foto-val" placeholder="O pega enlace de imagen (URL)" class="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-xs focus:border-amber-500 outline-none">
                    </div>

                    <div class="flex gap-2 pt-2">
                        <button type="submit" class="flex-1 py-2 bg-amber-500 text-gray-950 font-bold rounded-xl text-xs hover:bg-amber-400">Publicar</button>
                        <button type="button" onclick="toggleNewJobForm()" class="py-2 px-4 bg-gray-800 text-gray-300 font-bold rounded-xl text-xs">Cancelar</button>
                    </div>
                </form>

                <!-- LISTA DE OFERTAS EXISTENTES -->
                <div class="space-y-2">
                    {''.join([f'''
                    <div class="bg-gray-900 border border-gray-800 p-3 rounded-xl flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <img src="{o['foto']}" class="w-12 h-12 rounded-lg object-cover border border-gray-700">
                            <div>
                                <h4 class="font-bold text-sm">{o['titulo']}</h4>
                                <p class="text-xs text-amber-400">${o['sueldo_ofrecido']:,}</p>
                            </div>
                        </div>
                        <button onclick="deleteJob('{o['id']}')" class="text-xs text-red-400 hover:text-red-300 p-2">🗑️</button>
                    </div>
                    ''' for o in mis_ofertas])}
                </div>
            </div>
        </div>
        {NAV_BAR}

        <script>
        function convertFileToBase64(fileInput, targetId, previewImgId) {{
            const file = fileInput.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {{
                document.getElementById(targetId).value = e.target.result;
                if(previewImgId) document.getElementById(previewImgId).src = e.target.result;
            }};
            reader.readAsDataURL(file);
        }}

        function toggleNewJobForm() {{
            document.getElementById('new-job-form').classList.toggle('hidden');
        }}

        async function saveProfile(e) {{
            e.preventDefault();
            let payload = {{
                nombre: document.getElementById('edit-nombre').value,
                descripcion: document.getElementById('edit-desc').value,
                foto: document.getElementById('edit-foto').value,
                region: document.getElementById('edit-region').value,
                ciudad: document.getElementById('edit-ciudad').value,
                edad: document.getElementById('edit-edad') ? document.getElementById('edit-edad').value : null,
                expectativa_renta: document.getElementById('edit-renta') ? document.getElementById('edit-renta').value : null,
                habilidades: document.getElementById('edit-skills') ? document.getElementById('edit-skills').value : null,
                contacto: document.getElementById('edit-contacto') ? document.getElementById('edit-contacto').value : null,
                mensaje_bienvenida: document.getElementById('edit-welcome') ? document.getElementById('edit-welcome').value : null
            }};

            let r = await fetch('/api/update_profile', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(payload)
            }});
            let res = await r.json();
            if(res.status === 'ok') {{
                document.getElementById('save-status').classList.remove('hidden');
                setTimeout(() => document.getElementById('save-status').classList.add('hidden'), 3000);
            }}
        }}

        async function createNewJob(e) {{
            e.preventDefault();
            let payload = {{
                titulo: document.getElementById('job-title').value,
                descripcion: document.getElementById('job-desc').value,
                sueldo: document.getElementById('job-sueldo').value,
                habilidades: document.getElementById('job-skills').value,
                foto: document.getElementById('job-foto-val').value
            }};

            let r = await fetch('/api/create_job', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(payload)
            }});
            let res = await r.json();
            if(res.status === 'ok') location.reload(); else alert(res.msg);
        }}

        async function deleteJob(jobId) {{
            if(!confirm('¿Deseas eliminar esta oferta?')) return;
            let r = await fetch('/api/delete_job/' + jobId, {{ method: 'DELETE' }});
            let res = await r.json();
            if(res.status === 'ok') location.reload();
        }}
        </script>
    </body></html>"""
    return render_template_string(html)

@app.route("/api/update_profile", methods=["POST"])
def update_profile():
    u = session.get("user_id")
    if not u or u not in users_db:
        return jsonify({"status": "error", "msg": "No autorizado"}), 401
    
    data = request.json
    user = users_db[u]
    
    user["nombre"] = data.get("nombre", user["nombre"])
    user["descripcion"] = data.get("descripcion", user.get("descripcion", ""))
    if data.get("foto"): user["foto"] = data.get("foto")
    
    if "ubicacion" not in user: user["ubicacion"] = {"lat": -33.4489, "lon": -70.6693}
    user["ubicacion"]["region"] = data.get("region", user["ubicacion"].get("region", ""))
    user["ubicacion"]["ciudad"] = data.get("ciudad", user["ubicacion"].get("ciudad", ""))
    
    if user["role"] == "candidato":
        if data.get("edad"): user["edad"] = int(data["edad"])
        if data.get("expectativa_renta"): user["expectativa_renta"] = int(data["expectativa_renta"])
        if data.get("habilidades") is not None:
            user["habilidades"] = [h.strip() for h in data["habilidades"].split(",") if h.strip()]
    
    if user["role"] == "empleador":
        if data.get("contacto") is not None: user["contacto"] = data["contacto"]
        if data.get("mensaje_bienvenida") is not None: user["mensaje_bienvenida"] = data["mensaje_bienvenida"]

    return jsonify({"status": "ok"})

@app.route("/api/create_job", methods=["POST"])
def create_job():
    u = session.get("user_id")
    if not u or u not in users_db or users_db[u]["role"] != "empleador":
        return jsonify({"status": "error", "msg": "No autorizado"}), 401
    
    data = request.json
    user = users_db[u]
    
    nueva_oferta = {
        "id": f"job_{uuid.uuid4().hex[:6]}",
        "empleador_id": u,
        "titulo": data.get("titulo") or "Puesto Vacante",
        "empresa": user["nombre"],
        "descripcion": data.get("descripcion", ""),
        "edad_minima": 18,
        "ubicacion": user.get("ubicacion", {"lat": -33.4489, "lon": -70.6693, "region": "Región Metropolitana", "ciudad": "Santiago"}),
        "habilidades_requeridas": [h.strip() for h in data.get("habilidades", "").split(",") if h.strip()] or ["atencion_cliente"],
        "sueldo_ofrecido": int(data.get("sueldo") or 600000),
        "foto": data.get("foto") or user.get("foto")
    }
    
    ofertas_db.append(nueva_oferta)
    return jsonify({"status": "ok"})

@app.route("/api/delete_job/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    u = session.get("user_id")
    if not u: return jsonify({"status": "error"}), 401
    
    global ofertas_db
    ofertas_db = [o for o in ofertas_db if not (o["id"] == job_id and o["empleador_id"] == u)]
    return jsonify({"status": "ok"})

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "short_name": "PalApp",
        "name": "PalApp - Empleos y Talento",
        "icons": [
            {
                "src": "https://ui-avatars.com/api/?name=PalApp&background=f59e0b&color=fff&size=192",
                "type": "image/png",
                "sizes": "192x192",
                "purpose": "any maskable"
            },
            {
                "src": "https://ui-avatars.com/api/?name=PalApp&background=f59e0b&color=fff&size=512",
                "type": "image/png",
                "sizes": "512x512",
                "purpose": "any maskable"
            }
        ],
        "start_url": "/",
        "background_color": "#030712",
        "theme_color": "#f59e0b",
        "display": "standalone",
        "orientation": "portrait",
        "scope": "/"
    })

@app.route("/.well-known/assetlinks.json")
def assetlinks():
    return jsonify([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.barbermoon.palapp",
            "sha256_cert_fingerprints": [
                "70:BF:EB:2B:48:24:66:C9:93:11:DF:9D:4E:5C:08:D6:01:3A:F5:F4:2A:80:A9:E1:57:22:19:E4:57:CA:70:88"
            ]
        }
    }])

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
