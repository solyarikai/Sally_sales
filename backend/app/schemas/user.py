"""
Pydantic schemas for User, Environment, Company, and Activity Log
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


# ============ User Schemas ============

class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Environment Schemas ============

class EnvironmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)


class EnvironmentCreate(EnvironmentBase):
    pass


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)


class EnvironmentResponse(EnvironmentBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnvironmentWithStats(EnvironmentResponse):
    """Environment with company count"""
    companies_count: int = 0


# ============ Company Schemas ============

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    website: Optional[str] = Field(None, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')  # Hex color


class CompanyCreate(CompanyBase):
    environment_id: Optional[int] = None  # Can specify which environment


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    website: Optional[str] = Field(None, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    environment_id: Optional[int] = None  # Can move to different environment


class CompanyResponse(CompanyBase):
    id: int
    user_id: int
    environment_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompanyWithStats(CompanyResponse):
    """Company with statistics"""
    prospects_count: int = 0
    datasets_count: int = 0
    documents_count: int = 0


# ============ Activity Log Schemas ============

class ActivityLogBase(BaseModel):
    action: str = Field(..., max_length=100)
    entity_type: Optional[str] = Field(None, max_length=100)
    entity_id: Optional[int] = None
    details: Optional[dict] = None


class ActivityLogCreate(ActivityLogBase):
    user_id: int
    company_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ActivityLogResponse(ActivityLogBase):
    id: int
    user_id: int
    company_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityLogListResponse(BaseModel):
    logs: List[ActivityLogResponse]
    total: int
    page: int
    page_size: int


# ============ Common Response Schemas ============

class MessageResponse(BaseModel):
    message: str


class CurrentUserResponse(BaseModel):
    user: UserResponse
    environments: List[EnvironmentResponse]
    companies: List[CompanyResponse]
