# ============================================
# Backup automático de la base de datos (Windows)
# ============================================
# Ejecutar manualmente:
#   powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
#
# O programar en Tareas Programadas (ver SETUP_SERVIDOR.md)

$ErrorActionPreference = "Stop"

# Configuración
$CONTAINER = "citas_app"
$DB_PATH = "/app/data/citas.db"
$BACKUP_DIR = "C:\backups\citas"
$DIA = Get-Date -Format "yyyy-MM-dd"
$HORA = Get-Date -Format "HHmm"
$NOMBRE = "citas_${DIA}_${HORA}.db"
$KEEP_DAYS = 30

# Crear directorio si no existe
if (-not (Test-Path $BACKUP_DIR)) {
    New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
}

Write-Host "[$(Get-Date)] Iniciando backup..."

# Copiar la base de datos desde el contenedor
docker cp "${CONTAINER}:${DB_PATH}" "${BACKUP_DIR}\${NOMBRE}"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error al copiar la base de datos. ¿Está el contenedor corriendo?"
    exit 1
}

# Copiar archivos WAL y SHM si existen
docker cp "${CONTAINER}:${DB_PATH}-wal" "${BACKUP_DIR}\${NOMBRE}-wal" 2>$null
docker cp "${CONTAINER}:${DB_PATH}-shm" "${BACKUP_DIR}\${NOMBRE}-shm" 2>$null

# Verificar que el backup no está vacío
$TAMANO = (Get-Item "${BACKUP_DIR}\${NOMBRE}").Length
if ($TAMANO -lt 1024) {
    Write-Error "Backup sospechosamente pequeño ($TAMANO bytes)"
    exit 1
}

Write-Host "[$(Get-Date)] Backup creado: $NOMBRE ($TAMANO bytes)"

# Limpiar backups antiguos
Write-Host "[$(Get-Date)] Limpiando backups anteriores a $KEEP_DAYS días..."
$Limite = (Get-Date).AddDays(-$KEEP_DAYS)
Get-ChildItem "$BACKUP_DIR\citas_*.db" | Where-Object { $_.LastWriteTime -lt $Limite } | Remove-Item -Force
Get-ChildItem "$BACKUP_DIR\citas_*.db-wal" | Where-Object { $_.LastWriteTime -lt $Limite } | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem "$BACKUP_DIR\citas_*.db-shm" | Where-Object { $_.LastWriteTime -lt $Limite } | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "[$(Get-Date)] Backup completado."
