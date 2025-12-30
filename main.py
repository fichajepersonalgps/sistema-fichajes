import os
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Conexión a Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, dni: str = Form(...), password: str = Form(None)):
    # Buscamos por tu columna dni_nie
    res = supabase.table("trabajadores").select("*").eq("dni_nie", dni).execute()
    if not res.data:
        return templates.TemplateResponse("login.html", {"request": request, "error": "DNI no encontrado"})
    
    usuario = res.data[0]
    
    # Verificación de Admin (rol y password)
    if password: 
        if usuario.get("rol") == "admin" and usuario.get("password") == password:
            return RedirectResponse(url=f"/admin?admin_id={usuario['id']}", status_code=303)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Clave incorrecta"})

    return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": usuario})

@app.get("/admin")
async def admin_page(request: Request, admin_id: str, trabajador_id: str = None, mes: str = None):
    # Lista de trabajadores para el filtro (solo rol trabajador)
    trabajadores = supabase.table("trabajadores").select("*").neq("rol", "admin").execute().data
    
    # Consulta de fichajes vinculando con trabajadores
    query = supabase.table("fichajes").select("*, trabajadores(*)").order("fecha_hora", desc=True)
    
    if trabajador_id:
        query = query.eq("trabajador_id", trabajador_id)
    if mes:
        query = query.filter("fecha_hora", "gte", f"{mes}-01").filter("fecha_hora", "lt", f"{mes}-32")
    
    fichajes = query.execute().data
    
    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "trabajadores": trabajadores, 
        "fichajes": fichajes,
        "admin_id": admin_id,
        "filtro_trabajador": trabajador_id,
        "mes_actual": mes or datetime.now().strftime("%Y-%m")
    })

@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...), servicio: str = Form(...)):
    # Insertamos en la tabla fichajes usando tus columnas exactas
    supabase.table("fichajes").insert({
        "trabajador_id": worker_id, 
        "tipo": tipo, 
        "latitud": lat, 
        "longitud": lon, 
        "servicio": servicio 
    }).execute()
    return {"status": "ok"}