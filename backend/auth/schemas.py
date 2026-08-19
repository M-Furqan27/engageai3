from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)

    @field_validator("first_name", "last_name", "email")
    @classmethod
    def trim(cls, value: str):
        return value.strip()


class LoginRequest(BaseModel):
    email: str
    password: str
