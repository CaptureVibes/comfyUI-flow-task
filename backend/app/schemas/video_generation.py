import uuid
from pydantic import BaseModel

class VideoGenerationRequest(BaseModel):
    account_id: uuid.UUID
    template_id: uuid.UUID
    final_prompt: str
    image: str
    duration: str
    shots: list | None = None
