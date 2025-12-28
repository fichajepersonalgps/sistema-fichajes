import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuración de Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, dni: str = Form(...), password: str = Form(None)):
    # Buscamos al usuario por su DNI
    res = supabase.table("trabajadores").select("*").eq("dni_nie", dni).execute()
    
    if not res.data:
        return templates.TemplateResponse("login.html", {"request": request, "error": "DNI no encontrado"})
    
    usuario = res.data[0]

    # SI SE INTENTA LOGUEAR COMO ADMIN (rellenó el campo password)
    if password:
        # Verificamos rol y contraseña desde Supabase
        if usuario.get("rol") == "admin" and usuario.get("password") == password:
            res_fichajes = supabase.table("fichajes").select("*, trabajadores(nombre, apellidos, dni_nie)").order("fecha_hora", desc=True).execute()
            return templates.TemplateResponse("admin.html", {"request": request, "fichajes": res_fichajes.data})
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Contraseña incorrecta o no tienes permisos de Admin"})

    # LOGIN NORMAL DE TRABAJADOR
    return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": usuario})

@app.get("/admin")
async def admin_page(request: Request):
    # Acceso directo para el admin (puedes protegerlo más adelante)
    res = supabase.table("fichajes").select("*, trabajadores(nombre, apellidos, dni_nie)").order("fecha_hora", desc=True).execute()
    return templates.TemplateResponse("admin.html", {"request": request, "fichajes": res.data})

@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...), servicio: str = Form(...)):
    data = {"trabajador_id": worker_id, "tipo": tipo, "latitud": lat, "longitud": lon, "servicio": servicio}
    supabase.table("fichajes").insert(data).execute()
    return {"status": "ok"}