#!/bin/bash
# ============================================
# Backup automático de la base de datos
# ============================================
# Ejecutar con cron a las 3:00 AM todos los días:
#   crontab -e
#   0 3 * * * /ruta/citas_clinica/scripts/backup.sh
#
# O ejecutar manualmente:
#   bash scripts/backup.sh

set -euo pipefail

# Configuración
CONTAINER="citas_app"
DB_PATH="/app/data/citas.db"
BACKUP_DIR="/backups/citas"
DIA=$(date +%Y-%m-%d)
HORA=$(date +%H%M)
NOMBRE="citas_${DIA}_${HORA}.db"
KEEP_DAYS=30  # Mantener backups de los últimos 30 días

# Crear directorio si no existe
mkdir -p "$BACKUP_DIR"

# Copiar la base de datos desde el contenedor
echo "[$(date)] Iniciando backup..."
docker cp "${CONTAINER}:${DB_PATH}" "${BACKUP_DIR}/${NOMBRE}"
docker cp "${CONTAINER}:${DB_PATH}-wal" "${BACKUP_DIR}/${NOMBRE}-wal" 2>/dev/null || true
docker cp "${CONTAINER}:${DB_PATH}-shm" "${BACKUP_DIR}/${NOMBRE}-shm" 2>/dev/null || true

# Verificar que el backup no está vacío
TAMANO=$(stat -f%z "${BACKUP_DIR}/${NOMBRE}" 2>/dev/null || stat -c%s "${BACKUP_DIR}/${NOMBRE}" 2>/dev/null)
if [ "$TAMANO" -lt 1024 ]; then
    echo "[$(date)] ERROR: Backup sospechosamente pequeño (${TAMANO} bytes)"
    exit 1
fi

echo "[$(date)] Backup creado: ${NOMBRE} (${TAMANO} bytes)"

# Limpiar backups antiguos
echo "[$(date)] Limpiando backups anteriores a ${KEEP_DAYS} días..."
find "$BACKUP_DIR" -name "citas_*.db" -mtime +${KEEP_DAYS} -delete
find "$BACKUP_DIR" -name "citas_*.db-wal" -mtime +${KEEP_DAYS} -delete
find "$BACKUP_DIR" -name "citas_*.db-shm" -mtime +${KEEP_DAYS} -delete

echo "[$(date)] Backup completado."
