USERS_VIEW = "users:view"
USERS_CREATE = "users:create"
USERS_UPDATE = "users:update"
USERS_ACTIVATE = "users:activate"

ROLES_VIEW = "roles:view"
ROLES_ASSIGN = "roles:assign"

SOCIETIES_CREATE = "societies:create"
SOCIETIES_VIEW = "societies:view"

ALL_PERMISSIONS = [
    USERS_VIEW,
    USERS_CREATE,
    USERS_UPDATE,
    USERS_ACTIVATE,
    ROLES_VIEW,
    ROLES_ASSIGN,
    SOCIETIES_CREATE,
    SOCIETIES_VIEW,
]

ROLE_PERMISSIONS = {
    "super_admin": ALL_PERMISSIONS,
    "admin": [
        USERS_VIEW,
        USERS_CREATE,
        USERS_UPDATE,
        USERS_ACTIVATE,
        ROLES_VIEW,
        ROLES_ASSIGN,
        SOCIETIES_VIEW,
    ],
    "committee": [],
    "security_guard": [],
    "resident": [],
}