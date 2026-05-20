from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthUser(BaseModel):
    id: str
    email: EmailStr
    role: str


class LoginResponse(BaseModel):
    accessToken: str
    user: AuthUser


class LoginResponseEnvelope(BaseModel):
    success: bool = True
    data: LoginResponse
