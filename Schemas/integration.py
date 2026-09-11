"""Phase 18 request schemas."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DeviceRegisterRequest(BaseModel):
    deviceUid: str = Field(min_length=3, max_length=128)
    platform: str = Field(min_length=2, max_length=32)
    appId: str = "resident"
    appVersion: Optional[str] = None
    osVersion: Optional[str] = None
    fingerprintHash: Optional[str] = None
    pushToken: Optional[str] = None
    pushProvider: Optional[str] = None
    biometricEnabled: bool = False


class MobileLoginRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = None
    deviceUid: str
    platform: str
    appId: str = "resident"
    appVersion: Optional[str] = None
    osVersion: Optional[str] = None
    fingerprintHash: Optional[str] = None
    biometricEnabled: bool = False


class MobileRefreshRequest(BaseModel):
    refreshToken: str
    deviceUid: str


class MobileLogoutRequest(BaseModel):
    refreshToken: Optional[str] = None
    sessionId: Optional[UUID] = None


class PushRegisterRequest(BaseModel):
    deviceUid: str
    pushToken: str
    pushProvider: str = "fcm"


class SyncPushRequest(BaseModel):
    mutations: List[dict[str, Any]] = Field(default_factory=list)


class SyncPullRequest(BaseModel):
    cursor: Optional[str] = None
    collections: Optional[List[str]] = None


class DeepLinkResolveRequest(BaseModel):
    type: str
    id: Optional[str] = None
    code: Optional[str] = None


class MediaUploadRequest(BaseModel):
    filename: str
    contentType: str = "application/octet-stream"
    module: str = "general"
    providerCode: str = "minio"


class CrashReportRequest(BaseModel):
    message: str
    appId: Optional[str] = None
    appVersion: Optional[str] = None
    platform: Optional[str] = None
    deviceId: Optional[UUID] = None
    stackHash: Optional[str] = None
    breadcrumbs: Optional[List[Any]] = None


class WebhookSubscriptionCreate(BaseModel):
    name: str
    targetUrl: str
    events: List[str] = Field(default_factory=lambda: ["*"])
    societyId: Optional[UUID] = None
    maxAttempts: int = 8
    timeoutSeconds: int = 10


class WebhookSubscriptionUpdate(BaseModel):
    name: Optional[str] = None
    targetUrl: Optional[str] = None
    events: Optional[List[str]] = None
    status: Optional[str] = None


class PaymentIntentCreate(BaseModel):
    billId: UUID
    providerCode: str = "razorpay"
    idempotencyKey: Optional[str] = None


class PaymentRefundRequest(BaseModel):
    amountMinor: Optional[int] = None


class ApiClientCreate(BaseModel):
    name: str
    clientCode: str
    scopes: List[str] = Field(default_factory=list)
    societyId: Optional[UUID] = None
    description: Optional[str] = None
    rateLimitRpm: int = 120

    @field_validator("clientCode")
    @classmethod
    def code_ok(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("clientCode must be alphanumeric")
        return v.lower()


class ApiKeyCreate(BaseModel):
    clientId: UUID
    name: str = "default"
    scopes: Optional[List[str]] = None


class IdentityLinkRequest(BaseModel):
    provider: str
    subject: str
    email: Optional[str] = None
    profile: Optional[dict[str, Any]] = None


class ProviderHealthUpdate(BaseModel):
    status: str
    detail: Optional[str] = None


class PushSendRequest(BaseModel):
    deviceId: UUID
    title: str
    body: str
    data: Optional[dict[str, Any]] = None
    rich: bool = False
    silent: bool = False
    emergency: bool = False


class CommSendRequest(BaseModel):
    providerCode: str
    message: dict[str, Any]
