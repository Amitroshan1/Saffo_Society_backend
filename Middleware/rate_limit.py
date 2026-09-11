"""Rate limiting — replaces server/middleware/rateLimiter.js."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
