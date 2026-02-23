from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    email: str | None
    phone: str | None
    full_name: str
    role: str
    language_pref: str

    class Config:
        from_attributes = True
