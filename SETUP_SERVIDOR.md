# Setup del servidor propio en la clínica (Windows 11)

Guía completa para desplegar la aplicación de citas en un PC dedicado con Windows 11 dentro de la clínica.

## Requisitos previos

### Hardware
- PC con Windows 11 (el que ya compraste)
- 8GB+ RAM, 256GB+ SSD
- Conexión a internet con IP pública (o configuración de port forwarding)

### Software (se instala en el paso 1)
- Docker Desktop for Windows (usa WSL2 por debajo)
- Git for Windows

### Dominio (opcional pero recomendado)
- Un dominio apuntando a la IP pública del servidor
- Ejemplo: `citas.clinicamr.es`

---

## Paso 1: Preparar el PC (una vez)

### 1.1 Instalar Docker Desktop
1. Descargar Docker Desktop desde https://www.docker.com/products/docker-desktop/
2. Ejecutar el instalador
3. **Importante**: durante la instalación, asegurarse de que "Use WSL 2" está marcado
4. Reiniciar el PC cuando lo pida
5. Abrir Docker Desktop y esperar a que diga "Docker Desktop is running"

### 1.2 Instalar Git
1. Descargar desde https://git-scm.com/download/win
2. Instalar con opciones por defecto

### 1.3 Abrir puertos en el Firewall de Windows
1. Abrir "Windows Defender Firewall con seguridad avanzada"
2. Ir a "Reglas de entrada" → "Nueva regla"
3. Seleccionar "Puerto" → TCP → Puertos específicos: `80, 443`
4. Permitir la conexión
5. Aplicar a: Dominio, Privado, Público
6. Nombre: "Citas Clinica - HTTPS"
7. Repetir para puerto `8501` (solo si accedes desde dentro de la red local)

### 1.4 Configurar port forwarding en el router
1. Abrir el navegador y entrar en la configuración del router (normalmente `192.168.1.1` o `192.168.0.1`)
2. Buscar "Port Forwarding" o "Reenvío de puertos"
3. Añadir regla:
   - Puerto externo: `80` → IP interna del PC → puerto interno: `80`
   - Puerto externo: `443` → IP interna del PC → puerto interno: `443`
4. Guardar y reiniciar el router si hace falta

---

## Paso 2: Configurar la aplicación (una vez)

### 2.1 Clonar el código
1. Abrir PowerShell como administrador
2. Navegar a donde quieras guardar el proyecto:
```powershell
cd C:\
git clone https://github.com/CMROFTALMOLOGIA/citas-clinica.git
cd citas_clinica
```

### 2.2 Configurar las variables de entorno
```powershell
# Copiar el archivo de ejemplo
Copy-Item .env.example .env

# Abrir con el Bloc de notas
notepad .env
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

**IMPORTANTE**: Guardar y cerrar el Bloc de notas.

### 2.3 Configurar el dominio
Abrir `Caddyfile` con el Bloc de notas:
```powershell
notepad Caddyfile
```

Reemplazar `tudominio.com` con tu dominio real.

**Si NO tienes dominio todavía** (acceso directo por IP):
1. En `Caddyfile`, descomentar las últimas líneas (quitar los `#`)
2. Comentar las primeras líneas (añadir `#` al inicio)
3. Los navegadores mostrarán "No seguro" (certificado autofirmado)
4. Funciona igual, solo que sin candado verde

### 2.4 Poner los archivos de credenciales
Copiar los archivos de credenciales a la carpeta del proyecto:
```powershell
# Copiar desde donde los tengas guardados
Copy-Item "C:\Users\Manuel\OneDrive\mailing_credentials.json" .
Copy-Item "C:\Users\Manuel\OneDrive\sms_credentials.json" .
```

### 2.5 Hacer que Windows arranque la app automáticamente
1. Abrir "Tareas Programadas"
2. Crear tarea nueva:
   - Nombre: "Citas Clinica - Iniciar"
   - Activador: Al iniciar sesión
   - Acción: Programa/scrip → buscar `docker`
   - Argumentos: `compose -f C:\citas_clinica\docker-compose.yml up -d`
   - Iniciar en: `C:\citas_clinica`

---

## Paso 3: Levantar la aplicación

```powershell
cd C:\citas_clinica

# Construir y levantar (la primera vez tarda 5-10 minutos)
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

### 4.1 Crear carpeta de backups
```powershell
New-Item -ItemType Directory -Path "C:\backups\citas" -Force
```

### 4.2 Programar backup diario
1. Abrir "Tareas Programadas"
2. Crear tarea nueva:
   - Nombre: "Citas Clinica - Backup"
   - Activador: Diariamente a las 3:00 AM
   - Acción: Programa/scrip → `powershell.exe`
   - Argumentos: `-ExecutionPolicy Bypass -File "C:\citas_clinica\scripts\backup.ps1"`
3. En "Condiciones": desactivar "Detener si el ordenador pasa a estado de reposo"
4. En "Ajustes": marcar "Ejecutar tarea lo antes posible si se perdió el plan"

### 4.3 Backup manual (para probar)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
Get-ChildItem C:\backups\citas\
```

---

## Paso 5: Mantenimiento

### Acceso rápido al PC
Si necesitas controlar el PC a distancia desde tu PC principal:
1. Activar "Escritorio remoto" en el PC del servidor
   - Configuración → Sistema → Escritorio remoto → Activar
2. Desde tu PC: abrir "Conexión a Escritorio remoto" → poner la IP del PC del servidor

### Comandos útiles desde PowerShell
```powershell
cd C:\citas_clinica

# Ver estado
docker compose ps

# Ver logs de la app
docker compose logs -f app

# Ver logs de Caddy (accesos web)
docker compose logs -f caddy

# Reiniciar todo
docker compose restart

# Parar todo
docker compose down

# Actualizar (cuando haya cambios en GitHub)
git pull
docker compose up -d --build
```

### Restaurar backup
```powershell
# Parar la app
docker compose stop app

# Copiar el backup (ajustar la fecha)
Copy-Item "C:\backups\citas\citas_2026-08-25_0300.db" ".\data\citas.db"

# Reiniciar
docker compose start app
```

---

## Seguridad checklist

- [ ] PIN fuente cambiado (no `clinic2026`)
- [ ] Firewall activado solo puertos 80 y 443
- [ ] `.env` protegido (solo tu usuario puede leerlo)
- [ ] Backups funcionando y probados
- [ ] HTTPS activo con candado verde
- [ ] Windows Update activado y actualizado
- [ ] Escritorio remoto desactivado si no se usa

---

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Docker no arranca | Abrir Docker Desktop manualmente y esperar a que diga "Running" |
| No carga la página web | Verificar firewall: `Test-NetConnection -ComputerName localhost -Port 443` |
| No funciona HTTPS | Comprobar que el dominio apunta a la IP del servidor |
| Base de datos vacía | Los datos están en el volumen Docker; al recrear contenedor se mantienen |
| Backup falla | Verificar que el contenedor está corriendo: `docker compose ps` |
| PIN no funciona | Verificar `.env` tiene el PIN correcto: `Select-String CLINIC_PIN .env` |
| PC se suspende | Desactivar suspensión: Configuración → Sistema → Energía → Suspender → Nunca |

---

## Arquitectura final

```
Internet
    │
    ▼
┌─────────────────────────────┐
│  Router de la clínica       │
│  (port forwarding 80→PC)    │
└─────────────┬───────────────┘
              │
┌─────────────▼───────────────┐
│  PC (Windows 11)            │
│                             │
│  ┌─────────┐  ┌─────────┐  │
│  │ Caddy   │──│ App     │  │
│  │ :80/:443│  │ :8501   │  │
│  │ HTTPS   │  │ Streamlit│  │
│  └─────────┘  └────┬────┘  │
│                    │       │
│  Docker Desktop    │       │
│  (WSL2 Linux)      │       │
│                    │       │
│              ┌─────▼─────┐ │
│              │ citas.db   │ │
│              │ (SQLite)   │ │
│              └───────────┘ │
│                             │
│  C:\backups\citas\          │
│  (copias diarias)           │
└─────────────────────────────┘
```
