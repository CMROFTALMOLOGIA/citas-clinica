# Setup del servidor propio en la clínica

Guía completa para desplegar la aplicación de citas en un servidor dedicado dentro de la clínica.

## Requisitos previos

### Hardware
- Mini-PC o Raspberry Pi 4/5 (4GB+ RAM)
- 256GB+ SSD
- Conexión a internet con IP pública (o configuración de port forwarding)

### Software (se instala en el paso 1)
- Ubuntu Server 24.04 LTS
- Docker + Docker Compose
- Git

### Dominio (opcional pero recomendado)
- Un dominio apuntando a la IP pública del servidor
- Ejemplo: `citas.clinicamr.es`

---

## Paso 1: Preparar el servidor (una vez)

### 1.1 Instalar Ubuntu Server
1. Descargar Ubuntu Server 24.04 LTS desde https://ubuntu.com/download/server
2. Crear USB booteable con Rufus (Windows) o dd (Mac/Linux)
3. Arrancar el mini-PC desde USB y seguir el instalador
4. Anotar la IP local del servidor (ej: `192.168.1.100`)

### 1.2 Instalar Docker
```bash
# Conectar por SSH al servidor
ssh usuario@192.168.1.100

# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo apt install -y docker-compose-plugin

# Verificar
docker --version
docker compose version
```

### 1.3 Configurar el firewall
```bash
# Abrir puertos necesarios
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (redirige a HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

---

## Paso 2: Configurar la aplicación (una vez)

### 2.1 Copiar el código al servidor
```bash
# Desde tu PC local, copiar el proyecto
scp -r citas_clinica/ usuario@192.168.1.100:/home/usuario/

# O clonar desde GitHub
ssh usuario@192.168.1.100
git clone https://github.com/CMROFTALMOLOGIA/citas-clinica.git
cd citas_clinica
```

### 2.2 Configurar las variables de entorno
```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar con tus credenciales
nano .env
```

Rellenar cada variable:
```
CLINIC_PIN=TuPinSeguro2026!
AFILNET_USER=cmroftalmologia@gmail.com
AFILNET_PASS=tu_contraseña_afilnet
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=cmroftalmologia@gmail.com
SMTP_PASS=tu_app_password_gmail
SMTP_FROM=CMROFTALMOLOGIA
```

### 2.3 Configurar el dominio
Editar `Caddyfile` y reemplazar `tudominio.com` con tu dominio real:
```bash
nano Caddyfile
```

**Si NO tienes dominio todavía** (acceso directo por IP):
1. En `Caddyfile`, usar la versión comentada con `:443` y `tls internal`
2. Los navegadores mostrarán "No seguro" (certificado autofirmado)
3. Funciona igual, solo que sin candado verde

### 2.4 Poner los archivos de credenciales
```bash
# Copiar credenciales SMTP y SMS al directorio del proyecto
cp ~/mailing_credentials.json ./mailing_credentials.json
cp ~/sms_credentials.json ./sms_credentials.json
```

---

## Paso 3: Levantar la aplicación

```bash
cd citas_clinica

# Construir y levantar
docker compose up -d --build

# Verificar que funciona
docker compose ps
docker compose logs app
```

### 3.1 Verificar HTTPS
- Si tienes dominio: abrir `https://tudominio.com` → debe mostrar candado verde
- Si usas IP: abrir `https://192.168.1.100` → aceptar certificado autofirmado

### 3.2 Probar la zona clínica
1. Ir a la app → menú lateral → "Zona clínica"
2. Introducir el PIN configurado en `.env`
3. Verificar que funciona

---

## Paso 4: Configurar backups automáticos

### 4.1 Crear directorio de backups
```bash
sudo mkdir -p /backups/citas
sudo chmod 755 /backups/citas
```

### 4.2 Programar backup diario (cron)
```bash
# Abrir editor de crontab
crontab -e

# Añadir esta línea (backup a las 3:00 AM)
0 3 * * * /home/usuario/citas_clinica/scripts/backup.sh >> /var/log/backup-citas.log 2>&1
```

### 4.3 Backup manual (para probar)
```bash
bash scripts/backup.sh
ls -la /backups/citas/
```

---

## Paso 5: Mantenimiento

### Actualizar la aplicación
```bash
cd citas_clinica
git pull
docker compose up -d --build
```

### Ver logs
```bash
docker compose logs -f app      # Logs de la aplicación
docker compose logs -f caddy    # Logs de acceso web
```

### Reiniciar todo
```bash
docker compose restart
```

### Parar todo
```bash
docker compose down
```

### Restaurar backup
```bash
# Parar la app
docker compose stop app

# Copiar el backup
cp /backups/citas/citas_2026-08-25_0300.db ./data/citas.db

# Reiniciar
docker compose start app
```

---

## Seguridad checklist

- [ ] PIN fuente cambiado (no `clinic2026`)
- [ ] Firewall activado solo puertos 22, 80, 443
- [ ] `.env` con permisos `600` (solo el usuario puede leerlo)
- [ ] Backups funcionando y probados
- [ ] HTTPS activo con candado verde
- [ ] SSH con clave, no con contraseña
- [ ] Actualizaciones de seguridad programadas (`unattended-upgrades`)

### Hardening adicional (recomendado)
```bash
# Desactivar login por contraseña SSH (usar solo claves)
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /ssh/sshd_config
sudo systemctl restart sshd

# Instalar actualizaciones automáticas de seguridad
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Solución de problemas

| Problema | Solución |
|----------|----------|
| `docker: command not found` | Instalar Docker: `curl -fsSL https://get.docker.com \| sh` |
| No carga la página web | Verificar Caddy: `docker compose logs caddy` |
| No funciona HTTPS | Comprobar que el dominio apunta a la IP del servidor |
| Base de datos vacía | Los datos están en el volumen Docker; al recrear contenedor se mantienen |
| Backup falla | Verificar que el contenedor está corriendo: `docker compose ps` |
| PIN no funciona | Verificar `.env` tiene el PIN correcto: `grep CLINIC_PIN .env` |

---

## Arquitectura final

```
Internet
    │
    ▼
┌─────────────────────────────┐
│  Router de la clínica       │
│  (port forwarding 80→100)   │
└─────────────┬───────────────┘
              │
┌─────────────▼───────────────┐
│  Mini-PC (Ubuntu Server)    │
│                             │
│  ┌─────────┐  ┌─────────┐  │
│  │ Caddy   │──│ App     │  │
│  │ :80/:443│  │ :8501   │  │
│  │ HTTPS   │  │ Streamlit│  │
│  └─────────┘  └────┬────┘  │
│                    │       │
│              ┌─────▼─────┐ │
│              │ citas.db   │ │
│              │ (SQLite)   │ │
│              └───────────┘ │
│                             │
│  /backups/citas/            │
│  (copias diarias)           │
└─────────────────────────────┘
```
