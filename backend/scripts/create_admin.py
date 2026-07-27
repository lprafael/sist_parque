import asyncio
import os
import sys
from pathlib import Path

# Añadimos el directorio actual al PYTHONPATH para que encuentre app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models import Usuario
from passlib.context import CryptContext
from sqlalchemy import select

import bcrypt

async def create_admin():
    async with AsyncSessionLocal() as db:
        try:
            # Hash con bcrypt
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(b"admin123", salt).decode('utf-8')

            # Check if admin already exists
            result = await db.execute(select(Usuario).where(Usuario.username == "admin"))
            admin = result.scalar_one_or_none()
            
            if admin:
                admin.password_hash = hashed_password
                await db.commit()
                print("El usuario 'admin' ya existía; contraseña 'admin123' actualizada correctamente.")
            else:
                new_admin = Usuario(
                    username="admin",
                    email="admin@vmt.gov.py",
                    password_hash=hashed_password,
                    nombre_completo="Administrador VMT",
                    rol="ADMIN",
                    estado_usuario="ACTIVO"
                )
                db.add(new_admin)
                await db.commit()
                print("Usuario 'admin' creado exitosamente (Contraseña: admin123)")
                
        except Exception as e:
            print(f"Error creando admin: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_admin())
