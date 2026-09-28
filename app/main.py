from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.society.router import router as society_router
from auth.router import router as auth_router
from modules.resident.router import router as resident_router
from modules.visitor.router import router as visitor_router
from modules.vehicle.router import router as vehicle_router
from modules.sos.router import router as sos_router
from modules.facility.router import router as facility_router
from modules.clearance.router import router as clearance_router
from modules.notification.router import router as notification_router

app = FastAPI(title="Saffo Society API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(society_router)
app.include_router(resident_router)
app.include_router(visitor_router)
app.include_router(vehicle_router)
app.include_router(sos_router)
app.include_router(facility_router)
app.include_router(clearance_router)
app.include_router(notification_router)


@app.get("/health")
def health():
    return {"status": "ok"}