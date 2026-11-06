from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    email: str


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: str
    updated_at: str

    model_config = {
        "from_attributes": True
    }
