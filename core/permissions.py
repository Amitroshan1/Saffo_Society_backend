USERS_VIEW = "users:view"
USERS_CREATE = "users:create"
USERS_UPDATE = "users:update"
USERS_ACTIVATE = "users:activate"

ROLES_VIEW = "roles:view"
ROLES_ASSIGN = "roles:assign"

SOCIETIES_CREATE = "societies:create"
SOCIETIES_VIEW = "societies:view"

RESIDENT_VIEW = "resident:view"
RESIDENT_UPDATE = "resident:update"

VISITORS_VIEW = "visitors:view"
VISITORS_CREATE = "visitors:create"
VISITORS_UPDATE = "visitors:update"

SOS_VIEW = "sos:view"
SOS_CREATE = "sos:create"
SOS_CLOSE = "sos:close"

BOOKINGS_VIEW = "bookings:view"
BOOKINGS_CREATE = "bookings:create"
BOOKINGS_CANCEL = "bookings:cancel"

PARKING_VIEW = "parking:view"
PARKING_CREATE = "parking:create"
PARKING_UPDATE = "parking:update"

CLEARANCE_VIEW = "clearance:view"
CLEARANCE_CREATE = "clearance:create"
CLEARANCE_DUES = "clearance:dues"

NOTIFICATIONS_VIEW = "notifications:view"
NOTIFICATIONS_UPDATE = "notifications:update"

GUARD_VIEW = "guard:view"
GUARD_UPDATE = "guard:update"

GATE_VISITORS_VIEW = "gate_visitors:view"
GATE_VISITORS_CREATE = "gate_visitors:create"
GATE_VISITORS_UPDATE = "gate_visitors:update"

GATE_SOS_VIEW = "gate_sos:view"
GATE_SOS_UPDATE = "gate_sos:update"

GATE_BOOKINGS_VIEW = "gate_bookings:view"

STAFF_VIEW = "staff:view"
STAFF_UPDATE = "staff:update"

SCHEDULE_VIEW = "schedule:view"
SCHEDULE_UPDATE = "schedule:update"

GATE_PARKING_VIEW = "gate_parking:view"
GATE_PARKING_UPDATE = "gate_parking:update"

MOVE_OUT_VIEW = "move_out:view"
MOVE_OUT_UPDATE = "move_out:update"

DOCUMENTS_VIEW = "documents:view"

DELIVERIES_VIEW = "deliveries:view"
DELIVERIES_CREATE = "deliveries:create"
DELIVERIES_UPDATE = "deliveries:update"

CABS_VIEW = "cabs:view"
CABS_CREATE = "cabs:create"
CABS_UPDATE = "cabs:update"

RESIDENT_PERMISSIONS = [
    RESIDENT_VIEW, RESIDENT_UPDATE,
    VISITORS_VIEW, VISITORS_CREATE, VISITORS_UPDATE,
    SOS_VIEW, SOS_CREATE, SOS_CLOSE,
    BOOKINGS_VIEW, BOOKINGS_CREATE, BOOKINGS_CANCEL,
    PARKING_VIEW, PARKING_CREATE, PARKING_UPDATE,
    CLEARANCE_VIEW, CLEARANCE_CREATE,
    NOTIFICATIONS_VIEW, NOTIFICATIONS_UPDATE,
]
GUARD_PERMISSIONS = [
    GUARD_VIEW, GUARD_UPDATE,
    GATE_VISITORS_VIEW, GATE_VISITORS_CREATE, GATE_VISITORS_UPDATE,
    GATE_SOS_VIEW, GATE_SOS_UPDATE,
    GATE_BOOKINGS_VIEW,
    STAFF_VIEW, STAFF_UPDATE,
    SCHEDULE_VIEW, SCHEDULE_UPDATE,
    GATE_PARKING_VIEW, GATE_PARKING_UPDATE,
    MOVE_OUT_VIEW, MOVE_OUT_UPDATE,
    DOCUMENTS_VIEW,
    DELIVERIES_VIEW, DELIVERIES_CREATE, DELIVERIES_UPDATE,
    CABS_VIEW, CABS_CREATE, CABS_UPDATE,
]
ADMIN_PERMISSIONS = [
    USERS_VIEW, USERS_CREATE, USERS_UPDATE, USERS_ACTIVATE,
    ROLES_VIEW, ROLES_ASSIGN,
    SOCIETIES_VIEW,
    CLEARANCE_DUES,
]

ALL_PERMISSIONS = [
    *ADMIN_PERMISSIONS,
    SOCIETIES_CREATE,
    *RESIDENT_PERMISSIONS,
    *GUARD_PERMISSIONS,
]

ROLE_PERMISSIONS = {
    "super_admin": ALL_PERMISSIONS,
    "admin": ADMIN_PERMISSIONS,
    "committee": [],
    "security_guard": GUARD_PERMISSIONS,
    "resident": RESIDENT_PERMISSIONS,
}