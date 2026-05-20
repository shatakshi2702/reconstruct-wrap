from pydantic import BaseModel

class GenerateSchema(BaseModel):
    prompt: str
    type: str = "website"  # Options: "website", "text"
    current_code: str | None = None  # Optional for refinements
