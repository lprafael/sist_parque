# Sistema de Gestión de Parque Automotor — VMT Paraguay
## Walkthrough de Implementación

---

## ✅ Lo que está corriendo ahora mismo

| Servicio | URL | Estado |
|---|---|---|
| 🖥️ Frontend (React) | http://localhost:5173 | ✅ Activo |
| ⚙️ Backend (FastAPI) | http://localhost:8000 | ✅ Activo |
| 📖 API Docs (Swagger) | http://localhost:8000/docs | ✅ Activo |
| 🗄️ Base de Datos | `168.90.177.232:2024` → schema `registro_habilitacion` | ✅ Conectada |

---

## 📁 Estructura del Proyecto

```
sist_parque/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py         ← Login / JWT / refresh
│   │   │   ├── buses.py        ← CRUD buses + catálogos
│   │   │   ├── itv.py          ← ITV + historial
│   │   │   ├── seguros.py      ← Seguros + compañías
│   │   │   ├── empresas.py     ← EOTs (read-only) + asignaciones
│   │   │   ├── dashboard.py    ← KPIs + vencimientos + distribución
│   │   │   └── alertas.py      ← CRUD alertas + atender/ignorar
│   │   ├── core/
│   │   │   ├── config.py       ← pydantic-settings
│   │   │   ├── database.py     ← SQLAlchemy async engine
│   │   │   └── security.py     ← JWT + roles
│   │   ├── models/__init__.py  ← ORM: 14 tablas mapeadas
│   │   ├── schemas/__init__.py ← Pydantic schemas
│   │   ├── tasks/scheduler.py  ← APScheduler alertas diarias
│   │   └── main.py             ← FastAPI app
│   ├── migrations/
│   │   └── migrate_excel.py    ← Migración Excel → PostgreSQL
│   ├── .env                    ← Variables de entorno
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts       ← Axios + JWT interceptor
│   │   │   └── index.ts        ← Todos los endpoints
│   │   ├── stores/authStore.ts ← Zustand auth (persistido)
│   │   ├── components/
│   │   │   ├── Layout.tsx      ← App shell
│   │   │   └── Sidebar.tsx     ← Nav con badge de alertas
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── BusesPage.tsx
│   │   │   ├── EmpresasPage.tsx
│   │   │   └── AlertasPage.tsx
│   │   ├── index.css           ← Design system completo
│   │   └── App.tsx             ← Router + providers
│   └── Dockerfile
├── docker-compose.yml
└── .env.local                  ← Credenciales CID
```

---

## 🗄️ Datos Importantes

### Schema `registro_habilitacion` (14 tablas mapeadas)

| Tabla | Propósito |
|---|---|
| `buses` | Registro principal de vehículos |
| `marcas` | Catálogo marcas (M Benz, etc.) |
| `marcas_carroceria` | Catálogo marcas de carrocería |
| `tipos_carroceria` | Tipos de carrocería |
| `bus_empresa` | Asignaciones bus ↔ empresa (usa `id_eot_vmt_hex`) |
| `itv_bus` | Inspecciones técnicas vehiculares |
| `historial_itv` | Historial de cambios de ITV |
| `seguros_bus` | Seguros de pasajeros y terceros |
| `companias_seguros` | Catálogo de aseguradoras |
| `documentos_bus` | POD, RTD, habilitaciones |
| `alertas` | Alertas de vencimiento |
| `auditoria` | Log de todas las operaciones |
| `usuarios` | Usuarios del sistema |
| `auxiliar` | Staging para importación Excel |

### `public.eots` (READ-ONLY)
- **No se escribe** en esta tabla — es del sistema CID
- Se lee via `GET /api/v1/empresas`
- Las asignaciones usan `id_eot_vmt_hex` como FK en `bus_empresa`

---

## 🚀 Comandos para Levantar

### Desarrollo
```bash
# Backend
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (otra terminal)
cd frontend
npm run dev
```

### Producción (Docker)
```bash
docker-compose up -d --build
```

### Migración del Excel
```bash
cd backend
python3 migrations/migrate_excel.py --file "../ITV - 2026 Base de Datos 30-06-26.xlsx"
```

### Crear primer usuario admin
```sql
-- Ejecutar en la DB:
INSERT INTO registro_habilitacion.usuarios
    (username, email, password_hash, nombre_completo, rol)
VALUES (
    'admin',
    'admin@vmt.gov.py',
    -- Hash de la contraseña con bcrypt (generado con passlib)
    '$2b$12$...', 
    'Administrador VMT',
    'ADMIN'
);
```

> Para generar el hash desde Python:
> ```python
> from passlib.context import CryptContext
> pwd = CryptContext(schemes=["bcrypt"]).hash("tu_contraseña")
> print(pwd)
> ```

---

## 🔔 Alertas Automáticas

El scheduler se ejecuta **diariamente a las 07:00 (hora de Asunción)** y:
1. Escanea ITV con vencimiento en ≤30 días
2. Escanea seguros con vencimiento en ≤30 días
3. Crea registros en `registro_habilitacion.alertas`
4. Envía resumen por Gmail (configurar `SMTP_USER` y `SMTP_PASSWORD` en `.env`)

---

## 📋 Próximos Pasos

- [ ] Configurar Gmail App Password en `backend/.env` (SMTP_USER, SMTP_PASSWORD)
- [ ] Crear primer usuario admin con hash bcrypt
- [ ] Ejecutar migración del Excel
- [ ] Completar páginas ITV, Seguros y Reportes (actualmente en construcción)
- [ ] Agregar formulario de creación/edición de buses
- [ ] Build Docker para deploy en datacenter MOPC
