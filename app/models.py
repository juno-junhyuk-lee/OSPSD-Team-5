from pydantic import BaseModel


class Calendar(BaseModel):
    id: str
    title: str
    time_zone: str
