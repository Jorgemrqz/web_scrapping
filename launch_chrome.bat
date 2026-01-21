@echo off
set "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_PATH%" (
    set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)

if not exist "%CHROME_PATH%" (
    echo No se encontro Chrome en las rutas estandar.
    echo Por favor edita este archivo y pon la ruta correcta a chrome.exe
    pause
    exit /b
)

echo Lanzando Chrome con depuracion remota en puerto 9222...
echo PERFIL AGREGADO: Se usara una carpeta 'chrome_debug_profile' en este directorio para no mezclar con tu Chrome principal.
echo.
"%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%~dp0chrome_debug_profile"
