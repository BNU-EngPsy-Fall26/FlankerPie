@echo off
setlocal
cd /d "%~dp0"
echo.
echo  ============================================
echo   FlankerPie - push to GitHub
echo  ============================================
echo.
echo  Before you run this: create an EMPTY public repo on github.com,
echo  named FlankerPie. Do NOT tick "Add a README file".
echo.
if not "%~1"=="" ( set "URL=%~1" ) else ( set /p "URL=Repo URL (https://github.com/USER/FlankerPie.git): " )
if "%URL%"=="" goto :end
echo.
echo  Remote: %URL%
git remote remove origin >nul 2>nul
git remote add origin "%URL%"
git branch -M main
echo  Pushing (18 MB, first push may take 1-2 minutes)...
git push -u origin main
if errorlevel 1 (
  echo.
  echo  [X] Push failed. Check the URL ends with .git and the repo is empty.
  echo      If a GitHub sign-in window opened, finish signing in and run again.
  pause
  exit /b 1
)
echo.
echo  [OK] Code is on GitHub.
echo.
echo  Now turn on the website:
echo    1. Open your repo - Settings - Pages
echo    2. Build and deployment: Source = Deploy from a branch
echo    3. Branch = main , Folder = / (root) , click Save
echo    4. Wait 1-2 minutes, the page shows: Your site is live at ...
echo    5. That URL is your experiment link - send it to participants.
echo.
:end
pause
