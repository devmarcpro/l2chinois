@echo off
rem Publie les notes : commit + push. GitHub reconstruit le site en une a deux minutes.
chcp 65001 >nul
cd /d "%~dp0"
git add -A
git diff --cached --quiet
if not errorlevel 1 (
  echo Rien de nouveau a publier.
  pause
  exit /b 0
)
git commit -m "Notes du %date%"
git push
if errorlevel 1 (
  echo.
  echo Le push a echoue : verifie ta connexion ou ton identification GitHub.
) else (
  echo.
  echo Publie. Site a jour dans une a deux minutes : https://devmarcpro.github.io/l2chinois/
)
pause
