from pydantic import BaseModel


class SosOut(BaseModel):
    id: int
    title: str
    description: str
    photo_url: str | None
    category: str
    priority: str
    source: str
    status: str
    occupancy_id: int