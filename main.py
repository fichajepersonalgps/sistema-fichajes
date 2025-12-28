import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from supabase import create_client, Client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuración de Supabase mediante Variables de Entorno
# Estas se configuran en el panel de Vercel más adelante
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Esto es solo para que no falle si aún no has puesto las llaves en Vercel
    supabase = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- RUTAS DE NAVEGACIÓN ---

@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, dni: str = Form(...)):
    if not supabase:
        return "Error: Configura las variables de entorno en Vercel."
    
    # Buscar trabajador por DNI
    res = supabase.table("trabajadores").select("*").eq("dni_nie", dni).execute()
    
    if res.data:
        worker = res.data[0]
        # Al loguear con éxito, cargamos el panel del trabajador
        return templates.TemplateResponse("panel_trabajador.html", {"request": request, "worker": worker})
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "DNI no encontrado"})

@app.get("/chat")
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/admin")
async def admin_page(request: Request):
    # Obtenemos todos los fichajes junto con los datos del trabajador (Join)
    res = supabase.table("fichajes").select("*, trabajadores(nombre, apellidos, dni_nie)").order("fecha_hora", desc=True).execute()
    return templates.TemplateResponse("admin.html", {"request": request, "fichajes": res.data})

# --- RUTAS DE ACCIÓN (API) ---

@app.post("/fichar")
async def registrar_fichaje(
    worker_id: str = Form(...), 
    tipo: str = Form(...), 
    lat: float = Form(...), 
    lon: float = Form(...), 
    servicio: str = Form(...)
):
    try:
        data = {
            "trabajador_id": worker_id,
            "tipo": tipo,
            "latitud": lat,
            "longitud": lon,
            "servicio": servicio,
            "consentimiento_gps": True
        }
        supabase.table("fichajes").insert(data).execute()
        return {"status": "ok", "message": f"Registro de {tipo} guardado correctamente."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Para arrancar en local si quieres probar
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)