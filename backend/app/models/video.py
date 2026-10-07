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
    filename: str | None = Field(default=None, max_length=120)

class ClipRequest(DownloadRequest):
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    remove_silence: bool = False

class ArchiveItem(BaseModel):
    job_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1, max_length=120)
    srt: str | None = Field(default=None, max_length=200_000)

class ArchiveRequest(BaseModel):
    clips: list[ArchiveItem] = Field(min_length=1, max_length=100)
