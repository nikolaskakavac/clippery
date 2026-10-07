import re


def export_filename(value: str | None, fallback: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '_', value or '').strip(' .')
    name = re.sub(r'\.mp4$', '', name, flags=re.I).strip(' .')[:120]
    if not name:
        name = fallback
    if re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name):
        name = '_' + name
    return name + '.mp4'
