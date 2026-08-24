@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$inicio = [Environment]::GetFolderPath('Startup');" ^
  "$lnk = $ws.CreateShortcut(\"$inicio\MitraCheck Vivo.lnk\");" ^
  "$lnk.TargetPath = '%~dp0iniciar_mitracheck.bat';" ^
  "$lnk.WorkingDirectory = '%~dp0';" ^
  "$lnk.WindowStyle = 7;" ^
  "$lnk.Save()"
if errorlevel 1 (
    echo Falha ao criar o atalho de inicializacao.
    pause
    exit /b 1
)
echo Pronto! O MitraCheck Vivo iniciara automaticamente no seu login.
pause
