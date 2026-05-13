from app.core.config import settings
import cloudinary, asyncio
import cloudinary.uploader
from fastapi import UploadFile, HTTPException,status
from typing import List

if not settings.CLOUDINARY_CLOUD_NAME:
    raise RuntimeError("CLOUDINARY_CLOUD_NAME no está configurado")
if not settings.CLOUDINARY_API_KEY:
    raise RuntimeError("CLOUDINARY_API_KEY no está configurado")
if not settings.CLOUDINARY_API_SECRET:
    raise RuntimeError("CLOUDINARY_API_SECRET no está configurado")
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)
async def upload_single(file: UploadFile, folder:str):
    try:
        result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            file.file,
            folder=folder,
            resource_type="image"
        )
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"]
        }
    finally:
        await file.close()

async def upload_to_cloudinary(files: List[UploadFile], folder:str="products") -> list[dict]:
    tasks = [upload_single(file, folder) for file in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    images = []
    uploaded_public_ids = []
    for result in results:
        if isinstance(result, Exception):
            for public_id in uploaded_public_ids:
                try:
                    await asyncio.to_thread(
                        cloudinary.uploader.destroy,
                        public_id
                    )
                except Exception as e:
                    print(f"Error al enviar imagenes: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al subir imágenes. Operación revertida"
            )
        images.append(result)
        uploaded_public_ids.append(result["public_id"])
    return images

async def delete_from_cloudinary(public_id: str):
    try:
        result = await asyncio.to_thread(
            cloudinary.uploader.destroy,
            public_id
        )
        if result.get("result") != "ok":
            raise Exception("No se pudo eliminar la imagen")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando imagen: {str(e)}"
        )