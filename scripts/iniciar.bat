@echo off
echo ========================================
echo   Citas Clinica - Arrancando servidor
echo ========================================
echo.

cd /d C:\citas_clinica

echo Verificando Docker...
docker version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker no esta corriendo.
    echo Por favor, abre Docker Desktop y vuelve a intentar.
    pause
    exit /b 1
)

echo Docker OK. Construyendo y levantando contenedores...
echo (La primera vez tarda 5-10 minutos)
echo.
docker compose up -d --build

if errorlevel 1 (
    echo.
    echo ERROR: Fallo al levantar los contenedores.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Servidor arrancado correctamente
echo ========================================
echo.
echo App:    https://localhost
echo Logs:   docker compose logs -f
echo Parar:  docker compose down
echo.
pause
