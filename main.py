import os
import calendar
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
    if password and usuario.get("rol") == "admin" and usuario.get("password") == password:
        return RedirectResponse(url=f"/admin?admin_id={usuario['id']}", status_code=303)
    return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": usuario})

@app.get("/admin")
async def admin_page(request: Request, admin_id: str, trabajador_id: str = None, mes: str = None):
    try:
        trabajadores = supabase.table("trabajadores").select("*").neq("rol", "admin").execute().data
        if not mes: mes = datetime.now().strftime("%Y-%m")
        
        ano, mes_num = map(int, mes.split("-"))
        ultimo_dia = calendar.monthrange(ano, mes_num)[1]
        
        # Formatear nombre del mes en español
        meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        nombre_mes_formateado = f"{meses_es[mes_num-1]} {ano}"

        query = supabase.table("fichajes").select("*, trabajadores(*)").order("fecha_hora", desc=True)
        query = query.filter("fecha_hora", "gte", f"{mes}-01T00:00:00").filter("fecha_hora", "lte", f"{mes}-{ultimo_dia}T23:59:59")
        
        if trabajador_id: query = query.eq("trabajador_id", trabajador_id)
        
        res_fichajes = query.execute().data
        fichajes_procesados = []
        for f in res_fichajes:
            dt = datetime.fromisoformat(f['fecha_hora'].replace('Z', '+00:00')).astimezone(SPAIN_TZ)
            f['fecha_f'] = dt.strftime("%d/%m/%Y")
            f['hora_f'] = dt.strftime("%H:%M")
            f['ts'] = dt.timestamp()
            fichajes_procesados.append(f)

        return templates.TemplateResponse("admin.html", {
            "request": request, 
            "trabajadores": trabajadores, 
            "fichajes": fichajes_procesados,
            "admin_id": admin_id, 
            "filtro_trabajador": trabajador_id, 
            "mes_actual": mes,
            "mes_texto": nombre_mes_formateado
        })
    except Exception as e:
        return {"error": "Error de servidor", "detalle": str(e)}

@app.post("/fichar")
async def registrar_fichaje(worker_id: str = Form(...), tipo: str = Form(...), lat: float = Form(...), lon: float = Form(...), servicio: str = Form(...)):
    supabase.table("fichajes").insert({"trabajador_id": worker_id, "tipo": tipo, "latitud": lat, "longitud": lon, "servicio": servicio}).execute()
    return {"status": "ok"}