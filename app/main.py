from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.modules.products.router import router as products_router
from app.modules.contacts.router import router as email_router
from app.modules.auth.router import router as auth_router
from app.modules.carts.router import router as cart_router
from app.modules.orders.router import router as order_router
from app.modules.products_control.router import router as products_control_router
from app.modules.reclamations.router import router as reclamations_router
from app.modules.users_control.router import router as users_control_router
from app.core.scheduler import start_scheduler
from zoneinfo import ZoneInfo

DEFAULT_TZ = ZoneInfo("UTC")

origins = [
    "https://musitec-aqp.com",
    "https://musitec-aqp.vercel.app",
    "http://127.0.0.1:5173"
]

app = FastAPI(title="Musitec API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 
)
app.include_router(products_router)
app.include_router(email_router)
app.include_router(auth_router)
app.include_router(cart_router)
app.include_router(order_router)
app.include_router(products_control_router)
app.include_router(reclamations_router)
app.include_router(users_control_router)


@app.get("/")
async def root():
    return {"status": "ok"}


@app.middleware("http")
async def timezone_middleware(request: Request, call_next):
    tz_name = request.headers.get("X-Timezone")
    try:
        request.state.tz = ZoneInfo(tz_name) if tz_name else DEFAULT_TZ
    except Exception:
        request.state.tz = DEFAULT_TZ
    response = await call_next(request)
    return response

@app.on_event("startup")
async def startup_tasks():
    await start_scheduler()