@echo off
title Prospector RMI
rem Abre Prospector RMI en la laptop: enciende el servidor (con la geologia local) y la app si no estan encendidos,
rem espera a que respondan y abre el navegador. Para apagar: cerrar las ventanas minimizadas "Prospector - ...".
curl -s -o nul http://127.0.0.1:8000/health || start "Prospector - servidor" /min /D "%~dp0backend" venv\Scripts\python.exe -m uvicorn main:app --port 8000
curl -s -o nul http://localhost:5173/ || start "Prospector - app" /min /D "%~dp0frontend" cmd /c npx vite --port 5173 --strictPort
echo Abriendo Prospector RMI, espere unos segundos...
set /a intentos=0
:esperar
timeout /t 2 /nobreak >nul
set /a intentos+=1
if %intentos% gtr 60 goto fallo
curl -s -o nul http://localhost:5173/ || goto esperar
curl -s -o nul http://127.0.0.1:8000/health || goto esperar
start "" http://localhost:5173/
exit /b 0
:fallo
echo No se pudo encender Prospector RMI. Revise las ventanas "Prospector - servidor" y "Prospector - app".
pause
