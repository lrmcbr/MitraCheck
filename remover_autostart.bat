@echo off
chcp 65001 >nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MitraCheck Vivo.lnk" 2>nul
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MitraCheck Vivo.lnk" (
    echo Falha ao remover o atalho.
) else (
    echo Atalho removido. O sistema nao iniciara mais automaticamente.
)
pause
