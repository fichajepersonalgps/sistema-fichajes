import os
from datetime import datetime
import pytz
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuración
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SPAIN_TZ = pytz.timezone("Europe/Madrid")

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
    return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": usuario})

@app.get("/admin")
async def admin_page(request: Request, admin_id: str, trabajador_id: str = None, mes: str = None):
    try:
        # 1. Obtener lista de trabajadores para los filtros
        trabajadores = supabase.table("trabajadores").select("*").neq("rol", "admin").execute().data
        
        # 2. Construir consulta de fichajes
        query = supabase.table("fichajes").select("*, trabajadores(*)").order("fecha_hora", desc=True)
        
        # Filtrado por trabajador si se selecciona uno
        if trabajador_id and trabajador_id != "":
            query = query.eq("trabajador_id", trabajador_id)
        
        # Filtrado por mes
        if mes:
            query = query.filter("fecha_hora", "gte", f"{mes}-01").filter("fecha_hora", "lt", f"{mes}-32")
        
        fichajes_raw = query.execute().data
        
        # 3. Procesar zona horaria y formatos
        fichajes_procesados = []
        for f in fichajes_raw:
            dt = datetime.fromisoformat(f['fecha_hora'].replace('Z', '+00:00')).astimezone(SPAIN_TZ)
            f['fecha_f'] = dt.strftime("%d/%m/%Y")
            f['hora_f'] = dt.strftime("%H:%M")
            f['dt_obj'] = dt
            fichajes_procesados.append(f)

        return templates.TemplateResponse("admin.html", {
            "request": request, 
            "trabajadores": trabajadores, 
            "fichajes": fichajes_procesados,
            "admin_id": admin_id, 
            "filtro_trabajador": trabajador_id,
            "mes_actual": mes or datetime.now().strftime("%Y-%m")
        })
    except Exception as e:
        return {"error": "Internal Server Error", "detalle": str(e)}

@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...), servicio: str = Form(...)):
    supabase.table("fichajes").insert({
        "trabajador_id": worker_id, "tipo": tipo, "latitud": lat, "longitud": lon, "servicio": servicio 
    }).execute()
    return {"status": "ok"}