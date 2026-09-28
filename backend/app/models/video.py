from typing import Literal
from pydantic import BaseModel, Field, field_validator
from app.utils.validation import normalize_url

class VideoRequest(BaseModel):
    url: str = Field(max_length=2048)

    @field_validator('url')
    @classmethod
    def valid_url(cls, value: str) -> str:
        normalize_url(value)
        return value

class DownloadRequest(VideoRequest):
    quality: Literal['best', '1080', '720'] = '1080'

class ClipRequest(DownloadRequest):
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
