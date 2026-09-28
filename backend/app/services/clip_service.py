from app.services.download_service import process
from app.utils.time import validate_clip

def create_clip(url, quality, directory, update, start, end, duration):
    validate_clip(start, end, duration)
    return process(url, quality, directory, update, section=(start, end))
