"""
Scheduler de alertas automáticas — APScheduler
Se ejecuta diariamente a la hora configurada (ALERT_SCHEDULE_HOUR).
Genera alertas en registro_habilitacion.alertas para:
  - ITV próximos a vencer o vencidos
  - Seguros de pasajeros / terceros
  - Documentos (habilitación, POD/RTD)
"""
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="America/Asuncion")


async def generar_alertas():
    """Job principal: revisa vencimientos y crea/actualiza alertas."""
    from app.core.database import AsyncSessionLocal
    from app.models import ItvBus, SeguroBus, Alerta, Bus
    from sqlalchemy import select, and_

    hoy = date.today()
    async with AsyncSessionLocal() as db:
        try:
            alertas_generadas = 0

            # ---- ITV ----
            itv_q = await db.execute(
                select(ItvBus, Bus.rua, Bus.numero_orden)
                .join(Bus, Bus.id_bus == ItvBus.id_bus)
                .where(ItvBus.fecha_vencimiento <= hoy + timedelta(days=settings.ALERT_DAYS_INFO))
            )
            for itv, rua, orden in itv_q.all():
                diff = (itv.fecha_vencimiento - hoy).days
                prioridad = (
                    "ALTA" if diff <= settings.ALERT_DAYS_CRITICAL
                    else ("MEDIA" if diff <= settings.ALERT_DAYS_WARNING else "BAJA")
                )
                estado_txt = "VENCIDA" if diff < 0 else f"vence en {diff} días"
                titulo = f"ITV {estado_txt.upper()} — Bus {rua} (Orden #{orden})"

                # Evitar duplicados: no crear si ya hay una pendiente del mismo tipo+bus
                dup = await db.execute(
                    select(Alerta).where(
                        and_(
                            Alerta.id_bus == itv.id_bus,
                            Alerta.tipo_alerta == "ITV",
                            Alerta.estado_alerta == "PENDIENTE",
                            Alerta.fecha_alerta == hoy,
                        )
                    )
                )
                if not dup.scalar_one_or_none():
                    db.add(Alerta(
                        tipo_alerta="ITV",
                        id_bus=itv.id_bus,
                        titulo=titulo,
                        descripcion=(
                            f"La ITV del bus {rua} (Nro. Orden {orden}) "
                            f"{'venció el' if diff < 0 else 'vence el'} "
                            f"{itv.fecha_vencimiento.strftime('%d/%m/%Y')}. "
                            f"Resultado anterior: {itv.resultado_itv or 'N/A'}"
                        ),
                        fecha_alerta=hoy,
                        prioridad=prioridad,
                        estado_alerta="PENDIENTE",
                    ))
                    alertas_generadas += 1

            # ---- Seguros ----
            seg_q = await db.execute(
                select(SeguroBus, Bus.rua, Bus.numero_orden)
                .join(Bus, Bus.id_bus == SeguroBus.id_bus)
                .where(SeguroBus.fecha_vencimiento <= hoy + timedelta(days=settings.ALERT_DAYS_INFO))
            )
            for seg, rua, orden in seg_q.all():
                diff = (seg.fecha_vencimiento - hoy).days
                prioridad = (
                    "ALTA" if diff <= settings.ALERT_DAYS_CRITICAL
                    else ("MEDIA" if diff <= settings.ALERT_DAYS_WARNING else "BAJA")
                )
                tipo = f"SEGURO_{seg.tipo_seguro}"
                estado_txt = "VENCIDO" if diff < 0 else f"vence en {diff} días"

                dup = await db.execute(
                    select(Alerta).where(
                        and_(
                            Alerta.id_bus == seg.id_bus,
                            Alerta.tipo_alerta == tipo,
                            Alerta.estado_alerta == "PENDIENTE",
                            Alerta.fecha_alerta == hoy,
                        )
                    )
                )
                if not dup.scalar_one_or_none():
                    db.add(Alerta(
                        tipo_alerta=tipo,
                        id_bus=seg.id_bus,
                        titulo=f"Seguro {seg.tipo_seguro} {estado_txt.upper()} — Bus {rua}",
                        descripcion=(
                            f"El seguro de {seg.tipo_seguro} del bus {rua} "
                            f"{'venció el' if diff < 0 else 'vence el'} "
                            f"{seg.fecha_vencimiento.strftime('%d/%m/%Y')}. "
                            f"Póliza: {seg.numero_poliza or 'N/A'}"
                        ),
                        fecha_alerta=hoy,
                        prioridad=prioridad,
                        estado_alerta="PENDIENTE",
                    ))
                    alertas_generadas += 1

            await db.commit()
            logger.info(f"Scheduler: {alertas_generadas} alertas generadas [{hoy}]")

            # Enviar resumen por email si hay alertas críticas
            if alertas_generadas > 0:
                await enviar_resumen_email(db, alertas_generadas)

        except Exception as e:
            logger.error(f"Error en scheduler de alertas: {e}")
            await db.rollback()


async def enviar_resumen_email(db, total: int):
    """Envía resumen de alertas por Gmail SMTP."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP no configurado, omitiendo envío de email")
        return
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from app.models import Alerta
        from sqlalchemy import select, and_
        from datetime import date

        # Obtener alertas críticas del día
        criticas = (await db.execute(
            select(Alerta).where(
                and_(Alerta.prioridad == "ALTA", Alerta.fecha_alerta == date.today(), Alerta.estado_alerta == "PENDIENTE")
            )
        )).scalars().all()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[VMT Parque Automotor] {total} alertas generadas - {date.today().strftime('%d/%m/%Y')}"
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM}>"
        msg["To"] = settings.SMTP_USER

        html = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2 style="color:#1a237e;">🚌 Sistema de Parque Automotor — VMT Paraguay</h2>
        <p>Se generaron <strong>{total} alertas</strong> hoy {date.today().strftime('%d/%m/%Y')}.</p>
        <h3 style="color:#b71c1c;">⚠️ Alertas Críticas ({len(criticas)})</h3>
        <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
        <tr style="background:#1a237e;color:white;">
          <th>Tipo</th><th>Bus</th><th>Descripción</th>
        </tr>
        {"".join(f'<tr><td>{a.tipo_alerta}</td><td>Bus #{a.id_bus}</td><td>{a.titulo}</td></tr>' for a in criticas)}
        </table>
        <p><a href="http://localhost:5173/alertas">Ver todas las alertas en el sistema</a></p>
        <hr/><small>Generado automáticamente — No responder a este correo.</small>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Email de resumen enviado a {settings.SMTP_USER}")
    except Exception as e:
        logger.error(f"Error enviando email: {e}")


def start_scheduler():
    scheduler.add_job(
        generar_alertas,
        CronTrigger(
            hour=settings.ALERT_SCHEDULE_HOUR,
            minute=settings.ALERT_SCHEDULE_MINUTE,
            timezone="America/Asuncion"
        ),
        id="generar_alertas",
        replace_existing=True,
        name="Generación diaria de alertas de vencimiento"
    )
    scheduler.start()
    logger.info(
        f"Scheduler iniciado: alertas cada día a las "
        f"{settings.ALERT_SCHEDULE_HOUR:02d}:{settings.ALERT_SCHEDULE_MINUTE:02d} (Asunción)"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
