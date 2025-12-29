import os
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from supabase import create_client, Client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Conexión a Supabase
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# --- UTILIDADES ---
def obtener_estados_usuarios():
    # Obtiene el último fichaje de cada uno para ver quién está 'ENTRADA'
    fichajes = supabase.table("fichajes").select("trabajador_id, tipo").order("fecha_hora", desc=True).execute().data
    estados = {}
    for f in fichajes:
        if f['trabajador_id'] not in estados:
            estados[f['trabajador_id']] = f['tipo']
    return estados

# --- RUTAS DE ACCESO ---

@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, dni: str = Form(...), password: str = Form(None)):
    res = supabase.table("trabajadores").select("*").eq("dni_nie", dni).execute()
    if not res.data: return templates.TemplateResponse("login.html", {"request": request, "error": "DNI no encontrado"})
    
    usuario = res.data[0]
    if password: 
        if usuario.get("rol") == "admin" and usuario.get("password") == password:
            return RedirectResponse(url=f"/admin?admin_id={usuario['id']}", status_code=303)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Clave admin incorrecta"})

    return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": usuario})

# --- PANEL ADMIN CON FILTROS ---

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
        "request": request, 
        "trabajadores": trabajadores, 
        "fichajes": fichajes,
        "estados": estados,
        "admin_id": admin_id,
        "filtro_trabajador": trabajador_id,
        "mes_actual": mes or datetime.now().strftime("%Y-%m")
    })

# --- FICHAJE ---

@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...)):
    data = {"trabajador_id": worker_id, "tipo": tipo, "latitud": lat, "longitud": lon, "servicio": "General"}
    supabase.table("fichajes").insert(data).execute()
    return {"status": "ok"}

# --- CHAT EN TIEMPO REAL Y NOTIFICACIONES ---

@app.get("/chat_lista/{user_id}")
async def lista_chat(request: Request, user_id: str):
    trabajadores = supabase.table("trabajadores").select("*").neq("id", user_id).execute().data
    estados = obtener_estados_usuarios()
    return templates.TemplateResponse("lista_chat.html", {
        "request": request, "trabajadores": trabajadores, "estados": estados, "user_id": user_id
    })

@app.get("/chat/{receptor_id}")
async def ver_chat(request: Request, receptor_id: str, emisor_id: str):
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
        "emisor_id": emisor_id, 
        "receptor_id": receptor_id, 
        "contenido": contenido
    }).execute()
    return {"status": "ok"}

# RUTA PARA EL GLOBO DE NOTIFICACIÓN
@app.get("/mensajes_nuevos/{user_id}")
async def chequear_mensajes(user_id: str):
    # Devuelve los últimos 5 mensajes recibidos por este usuario para avisarle si hay algo nuevo
    res = supabase.table("chat_mensajes").select("*").eq("receptor_id", user_id).order("created_at", desc=True).limit(5).execute()
    return {"mensajes": res.data}