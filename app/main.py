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

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from modules.guard_common.settings import UPLOAD_DIRS
from modules.guard_visitor.router import router as guard_visitor_router
from modules.guard_sos.router import router as guard_sos_router
from modules.guard_booking.router import router as guard_booking_router
from modules.guard_dashboard.router import router as guard_dashboard_router
from modules.guard_profile.router import router as guard_profile_router
from modules.staff.router import router as staff_router
from modules.schedule.router import router as schedule_router
from modules.parking.router import router as parking_router
from modules.move_out.router import router as move_out_router
from modules.document.router import router as document_router
from modules.delivery.router import router as delivery_router
from modules.cab.router import router as cab_router
from modules.guard_common.router import router as guard_common_router

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

for guard_router in (
    guard_visitor_router, guard_sos_router, guard_booking_router, guard_dashboard_router,
    guard_profile_router, staff_router, schedule_router, parking_router,
    move_out_router, document_router, delivery_router, cab_router, guard_common_router,
):
    app.include_router(guard_router)
for folder in UPLOAD_DIRS:
    Path(folder).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/health")
def health():
    return {"status": "ok"}