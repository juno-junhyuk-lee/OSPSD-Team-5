from datetime import datetime

from pydantic import BaseModel


class Event(BaseModel):
    id: str
    title: str
    start_time: datetime
    end_time: datetime
