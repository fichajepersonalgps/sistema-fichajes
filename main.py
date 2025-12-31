import os
from datetime import datetime
import pytz
import calendar  # IMPORTANTE: Para calcular el último día del mes
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuración de Entorno
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
        # 1. Lista de trabajadores para el desplegable
        trabajadores = supabase.table("trabajadores").select("*").neq("rol", "admin").execute().data
        
        # 2. Gestión de fechas segura (Evita el error del día 32)
        if not mes:
            mes = datetime.now().strftime("%Y-%m")
        
        ano, mes_num = map(int, mes.split("-"))
        ultimo_dia = calendar.monthrange(ano, mes_num)[1]
        
        # Rango de fechas ISO para Supabase
        fecha_inicio = f"{mes}-01T00:00:00"
        fecha_fin = f"{mes}-{ultimo_dia}T23:59:59"

        # 3. Consulta de fichajes con join a trabajadores
        query = supabase.table("fichajes").select("*, trabajadores(*)").order("fecha_hora", desc=True)
        query = query.filter("fecha_hora", "gte", fecha_inicio).filter("fecha_hora", "lte", fecha_fin)
        
        if trabajador_id and trabajador_id != "":
            query = query.eq("trabajador_id", trabajador_id)
        
        res_fichajes = query.execute().data
        
        # 4. Procesamiento de horas (Madrid TZ)
        fichajes_procesados = []
        for f in res_fichajes:
            # Convertir UTC de Supabase a Madrid
            dt_utc = datetime.fromisoformat(f['fecha_hora'].replace('Z', '+00:00'))
            dt_madrid = dt_utc.astimezone(SPAIN_TZ)
            f['fecha_f'] = dt_madrid.strftime("%d/%m/%Y")
            f['hora_f'] = dt_madrid.strftime("%H:%M")
            f['dt_obj'] = dt_madrid
            fichajes_procesados.append(f)

        return templates.TemplateResponse("admin.html", {
            "request": request, 
            "trabajadores": trabajadores, 
            "fichajes": fichajes_procesados,
            "admin_id": admin_id, 
            "filtro_trabajador": trabajador_id,
            "mes_actual": mes
        })
    except Exception as e:
        return {"error": "Internal Server Error", "detalle": str(e)}

@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...), servicio: str = Form(...)):
    supabase.table("fichajes").insert({
        "trabajador_id": worker_id, 
        "tipo": tipo, 
        "latitud": lat, 
        "longitud": lon, 
        "servicio": servicio 
    }).execute()
    return {"status": "ok"}