from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: str
    email: str | None
    phone: str | None
    full_name: str
    role: str
    language_pref: str

    model_config = ConfigDict(from_attributes=True)
