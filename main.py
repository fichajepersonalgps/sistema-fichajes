import os
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client

app = FastAPI()

# CONFIGURACIÓN DE CARPETAS ESTÁTICAS (Crítico para PWA y Sonidos)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Conexión a Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- UTILIDADES ---
def obtener_estados_usuarios():
    fichajes = supabase.table("fichajes").select("trabajador_id, tipo").order("fecha_hora", desc=True).execute().data
    estados = {}
    for f in fichajes:
        if f['trabajador_id'] not in estados:
            estados[f['trabajador_id']] = f['tipo']
    
    admins = supabase.table("trabajadores").select("id").eq("rol", "admin").execute().data
    for a in admins:
        estados[a['id']] = 'ENTRADA'
    return estados

# --- RUTAS DE ACCESO ---
@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, dni: str = Form(...), password: str = Form(None)):
    res = supabase.table("trabajadores").select("*").eq("dni_nie", dni).execute()
    if not res.data:
        return templates.TemplateResponse("login.html", {"request": request, "error": "DNI no encontrado"})
    
    usuario = res.data[0]
    if password: 
        if usuario.get("rol") == "admin" and usuario.get("password") == password:
            return RedirectResponse(url=f"/admin?admin_id={usuario['id']}", status_code=303)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Clave incorrecta"})

    return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": usuario})

# --- PANEL ADMINISTRADOR ---
@app.get("/admin")
async def admin_page(request: Request, admin_id: str = None, trabajador_id: str = None, mes: str = None):
    trabajadores = supabase.table("trabajadores").select("*").execute().data
    estados = obtener_estados_usuarios()
    query = supabase.table("fichajes").select("*, trabajadores(*)").order("fecha_hora", desc=True)
    
    if trabajador_id:
        query = query.eq("trabajador_id", trabajador_id)
    if mes:
        query = query.filter("fecha_hora", "gte", f"{mes}-01").filter("fecha_hora", "lt", f"{mes}-31")
    
    fichajes = query.execute().data
    return templates.TemplateResponse("admin.html", {
        "request": request, "trabajadores": trabajadores, "fichajes": fichajes,
        "estados": estados, "admin_id": admin_id, "filtro_trabajador": trabajador_id,
        "mes_actual": mes or datetime.now().strftime("%Y-%m")
    })

# --- GESTIÓN DE FICHAJES (GPS) ---
@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...)):
    supabase.table("fichajes").insert({
        "trabajador_id": worker_id, "tipo": tipo, "latitud": lat, "longitud": lon, "servicio": "General"
    }).execute()
    return {"status": "ok"}

# --- SISTEMA DE CHAT ---
@app.get("/chat_lista/{user_id}")
async def lista_chat(request: Request, user_id: str):
    trabajadores = supabase.table("trabajadores").select("*").neq("id", user_id).execute().data
    estados = obtener_estados_usuarios()
    usuario_actual = supabase.table("trabajadores").select("rol").eq("id", user_id).single().execute().data
    return templates.TemplateResponse("lista_chat.html", {
        "request": request, "trabajadores": trabajadores, "estados": estados, 
        "user_id": user_id, "es_admin": usuario_actual['rol'] == 'admin'
    })

@app.get("/chat/{receptor_id}")
async def ver_chat(request: Request, receptor_id: str, emisor_id: str):
    supabase.table("chat_mensajes").update({"leido": True}).eq("emisor_id", receptor_id).eq("receptor_id", emisor_id).execute()
    
    mensajes = supabase.table("chat_mensajes").select("*").or_(
        f"and(emisor_id.eq.{emisor_id},receptor_id.eq.{receptor_id}),"
        f"and(emisor_id.eq.{receptor_id},receptor_id.eq.{emisor_id})"
    ).order("created_at").execute()
    
    receptor = supabase.table("trabajadores").select("*").eq("id", receptor_id).single().execute().data
    emisor = supabase.table("trabajadores").select("rol").eq("id", emisor_id).single().execute().data
    url_volver = f"/admin?admin_id={emisor_id}" if emisor['rol'] == 'admin' else f"/chat_lista/{emisor_id}"

    return templates.TemplateResponse("chat.html", {
        "request": request, "mensajes": mensajes.data, "receptor": receptor, "emisor_id": emisor_id, "url_volver": url_volver
    })

@app.post("/enviar_mensaje")
async def enviar(emisor_id: str = Form(...), receptor_id: str = Form(...), contenido: str = Form(...)):
    supabase.table("chat_mensajes").insert({
        "emisor_id": emisor_id, "receptor_id": receptor_id, "contenido": contenido, "leido": False
    }).execute()
    return {"status": "ok"}

@app.get("/mensajes_nuevos/{user_id}")
async def chequear_mensajes(user_id: str):
    res = supabase.table("chat_mensajes").select("*").eq("receptor_id", user_id).eq("leido", False).execute()
    return {"mensajes": res.data}