from flask import Flask, render_template_string, jsonify, request
import math
from datetime import datetime

app = Flask(__name__)

candidato = {
    "nombre": "Juan Pérez",
    "edad": 22,
    "expectativa_renta": 550000,
    "habilidades": ["atencion_cliente", "caja"],
    "ubicacion": {"lat": -33.4489, "lon": -70.6693}
}

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

mensajes = []

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
    <a href="/chat/candidato" class="flex flex-col items-center hover:text-amber-500">
        <span class="text-lg">💬</span>Chat
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
        <p class="text-gray-400 text-sm mt-1 mb-8">Conecta candidatos y empleadores en segundos</p>
        
        <div class="space-y-3">
            <a href="/candidato/feed" class="block w-full py-3.5 px-4 bg-amber-500 hover:bg-amber-600 text-gray-950 font-bold rounded-xl shadow-md transition">🔥 Explora Ofertas (Swipe)</a>
            <a href="/chat/candidato" class="block w-full py-3.5 px-4 bg-gray-800 hover:bg-gray-700 font-semibold rounded-xl transition">💬 Chat en Vivo</a>
            <a href="/candidato/perfil" class="block w-full py-3 px-4 bg-gray-900 border border-gray-800 text-gray-300 font-medium rounded-xl transition">👤 Perfil Candidato</a>
            <a href="/empleador" class="block w-full py-3 px-4 bg-gray-900 border border-gray-800 text-gray-300 font-medium rounded-xl transition">🏢 Panel Empleador</a>
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
        <h2 class="text-xl font-bold mb-4 text-center">Ofertas de Trabajo</h2>
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
            c.innerHTML='<div class="text-center py-10"><p class="text-4xl mb-2">🎉</p><p class="font-bold">¡No hay más ofertas!</p><p class="text-xs text-gray-400 mt-1">Vuelve más tarde para ver nuevos puestos</p></div>';
            a.classList.add('hidden'); return;
        }}
        let o=items[idx]; a.classList.remove('hidden');
        c.innerHTML='<div><div class="flex justify-between items-start mb-2"><span class="bg-amber-500/10 text-amber-500 border border-amber-500/20 text-xs px-2.5 py-1 rounded-full font-bold">'+o.match+'% Match</span><span class="text-xs text-gray-400">CLP $'+o.sueldo_ofrecido.toLocaleString('es-CL')+'</span></div><h3 class="text-lg font-bold text-white mb-1">'+o.titulo+'</h3><p class="text-sm text-gray-400 mb-4">'+o.empresa+'</p><div class="flex flex-wrap gap-1.5 mb-2">'+o.habilidades_requeridas.map(h=>'<span class="bg-gray-800 text-gray-300 text-[10px] px-2 py-0.5 rounded">'+h+'</span>').join('')+'</div></div>';
    }}
    function next(ok){{if(ok)location.href='/chat/candidato'; else{{idx++;show();}}}}
    </script>
</body>
</html>
"""

HTML_CHAT = f"""
<!DOCTYPE html>
<html lang="es">
{HTML_HEAD}
<body class="bg-gray-950 text-white h-screen flex flex-col pb-16">
    <div class="p-4 border-b border-gray-800 bg-gray-900 flex justify-between items-center">
        <h1 class="font-bold">💬 Chat</h1>
        <select id="emisor" class="bg-gray-800 text-xs px-2 py-1 rounded border border-gray-700 text-gray-300">
            <option value="candidato" {{ 'selected' if rol=='candidato' else '' }}>Soy Candidato</option>
            <option value="empleador" {{ 'selected' if rol=='empleador' else '' }}>Soy Empleador</option>
        </select>
    </div>
    <div id="msgs" class="flex-1 overflow-y-auto p-4 space-y-3"></div>
    <form onsubmit="send(event)" class="p-3 bg-gray-900 border-t border-gray-800 flex gap-2">
        <input id="txt" class="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-amber-500" placeholder="Escribe un mensaje..." required>
        <button type="submit" class="bg-amber-500 text-gray-950 px-4 py-2 rounded-xl font-bold text-sm">Enviar</button>
    </form>
    {NAV_BAR}
    <script>
    async function load(){{
        let r=await fetch('/api/mensajes'), d=await r.json(), c=document.getElementById('msgs');
        c.innerHTML=d.map(m=>'<div class="flex flex-col '+(m.emisor==='candidato'?'items-end':'items-start')+'"><div class="max-w-[80%] rounded-2xl px-4 py-2 text-sm '+(m.emisor==='candidato'?'bg-amber-500 text-gray-950 font-medium rounded-br-none':'bg-gray-800 text-white rounded-bl-none')+'"><p class="text-[10px] opacity-60 mb-0.5">'+m.emisor+'</p><p>'+m.texto+'</p></div><span class="text-[9px] text-gray-500 mt-0.5 px-1">'+m.hora+'</span></div>').join('');
        c.scrollTop=c.scrollHeight;
    }}
    async function send(e){{
        e.preventDefault(); let t=document.getElementById('txt'), em=document.getElementById('emisor').value;
        await fetch('/api/mensajes',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{emisor:em,texto:t.value}})}});
        t.value=''; load();
    }}
    load(); setInterval(load,2000);
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
        <h2 class="text-lg font-bold mb-4">👤 Mi Perfil Candidato</h2>
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
        alert("¡Perfil Guardado!");
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

@app.route("/")
def home():
    return render_template_string(HTML_HOME)

@app.route("/candidato/feed")
def candidato_feed():
    return render_template_string(HTML_FEED)

@app.route("/candidato/perfil")
def candidato_perfil():
    return render_template_string(HTML_CANDIDATO_PERFIL, cand=candidato)

@app.route("/empleador")
def vista_empleador():
    return render_template_string(HTML_EMPLEADOR, emp=perfil_empleador)

@app.route("/chat/candidato")
def chat_candidato():
    return render_template_string(HTML_CHAT, rol="candidato")

@app.route("/chat/empleador")
def chat_empleador():
    return render_template_string(HTML_CHAT, rol="empleador")

@app.route("/api/ofertas", methods=["GET"])
def get_ofertas():
    res = []
    for o in ofertas:
        item = dict(o)
        item["match"] = calcular_match(candidato, o)
        res.append(item)
    res.sort(key=lambda x: x["match"], reverse=True)
    return jsonify(res)

@app.route("/api/perfil-candidato", methods=["POST"])
def update_perfil_candidato():
    data = request.json or {}
    if "nombre" in data: candidato["nombre"] = data["nombre"]
    if "edad" in data: candidato["edad"] = int(data["edad"])
    if "expectativa_renta" in data: candidato["expectativa_renta"] = int(data["expectativa_renta"])
    if "habilidades" in data:
        raw = data["habilidades"]
        candidato["habilidades"] = [h.strip() for h in raw.split(",") if h.strip()] if isinstance(raw, str) else raw
    return jsonify({"status": "ok"})

@app.route("/api/perfil-empleador", methods=["POST"])
def update_perfil_empleador():
    data = request.json or {}
    if "nombre_empresa" in data:
        perfil_empleador["nombre_empresa"] = data["nombre_empresa"]
        for o in ofertas:
            o["empresa"] = data["nombre_empresa"]
    if "rut_empresa" in data: perfil_empleador["rut_empresa"] = data["rut_empresa"]
    if "contacto" in data: perfil_empleador["contacto"] = data["contacto"]
    return jsonify({"status": "ok"})

@app.route("/api/crear-empleo", methods=["POST"])
def crear_empleo():
    data = request.json or {}
    skills_raw = data.get("habilidades", "")
    skills = [h.strip() for h in skills_raw.split(",") if h.strip()] if isinstance(skills_raw, str) else skills_raw
    nuevo_job = {
        "id": f"job_{len(ofertas) + 101}",
        "titulo": data.get("titulo", "Puesto Nuevo"),
        "empresa": perfil_empleador["nombre_empresa"],
        "edad_minima": 18,
        "ubicacion": {"lat": -33.4489, "lon": -70.6693},
        "habilidades_requeridas": skills,
        "sueldo_ofrecido": int(data.get("sueldo_ofrecido", 500000))
    }
    ofertas.append(nuevo_job)
    return jsonify({"status": "ok"})

@app.route("/api/mensajes", methods=["GET", "POST"])
def api_mensajes():
    if request.method == "POST":
        data = request.json or {}
        mensajes.append({
            "emisor": data.get("emisor", "candidato"),
            "texto": data.get("texto", ""),
            "hora": datetime.now().strftime("%H:%M")
        })
        return jsonify({"status": "ok"})
    return jsonify(mensajes)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
