import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image,ImageOps

PROFILE_PIC_DIR=Path("media/profile_pics")

def process_profile_img(content: bytes)->str:
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)

        img = ImageOps.fit(img,(300,300),method=Image.Resampling.LANCZOS)
    
    if img.mode in ("RGBA","LA","P"):
        img = img.convert("RGB")

    file_name = f'{uuid.uuid4().hex}.jpg'
    file_path = PROFILE_PIC_DIR / file_name

    PROFILE_PIC_DIR.mkdir(parents=True,exist_ok=True)
    img.save(file_path,"JPEG",quality=85,optimize=True)
    return file_name

def delete_profile_image(filename: str | None)-> None:
    if filename  is None:
        return 
    
    filepath = PROFILE_PIC_DIR / filename
    if filepath.exists():
        filepath.unlink()