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

@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, dni: str = Form(...), password: str = Form(None)):
    res = supabase.table("trabajadores").select("*").eq("dni_nie", dni).execute()
    if not res.data:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Usuario no encontrado"})
    
    usuario = res.data[0]
    # Si es admin y pone clave, va al panel de control
    if password and usuario.get("rol") == "admin" and usuario.get("password") == password:
        return RedirectResponse(url="/admin", status_code=303)
    
    # Si es trabajador, va a su panel de fichaje
    return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": usuario})

@app.get("/admin")
async def admin_page(request: Request, mes: str = None):
    # Buscador por mes para reportes
    query = supabase.table("fichajes").select("*, trabajadores(*)").order("fecha_hora", desc=True)
    if mes:
        query = query.filter("fecha_hora", "gte", f"{mes}-01").filter("fecha_hora", "lt", f"{mes}-31")
    
    fichajes = query.execute().data
    return templates.TemplateResponse("admin.html", {"request": request, "fichajes": fichajes, "mes_filtro": mes})

@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...)):
    data = {"trabajador_id": worker_id, "tipo": tipo, "latitud": lat, "longitud": lon, "servicio": "General"}
    supabase.table("fichajes").insert(data).execute()
    return {"status": "ok"}

# RUTA DEL CHAT (Adaptada a tus columnas: emisor_id, receptor_id)
@app.get("/chat/{worker_id}")
async def ver_chat(request: Request, worker_id: str):
    mensajes = supabase.table("chat_mensajes").select("*").or_(f"emisor_id.eq.{worker_id},receptor_id.eq.{worker_id}").order("created_at").execute()
    worker = supabase.table("trabajadores").select("*").eq("id", worker_id).single().execute()
    return templates.TemplateResponse("chat.html", {"request": request, "mensajes": mensajes.data, "worker": worker.data})

@app.post("/enviar_mensaje")
async def enviar(emisor_id: str = Form(...), receptor_id: str = Form(...), contenido: str = Form(...)):
    supabase.table("chat_mensajes").insert({"emisor_id": emisor_id, "receptor_id": receptor_id, "contenido": contenido}).execute()
    return {"status": "ok"}