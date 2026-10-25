@echo off
setlocal
REM Builds the Android app (APK) with Flutter. It is a thin wrapper around the hosted Tim-Tim web app, so every feature matches the website.
REM Optional: set APP_URL first if your web app address is different:   set APP_URL=https://your-address.onrender.com
cd /d "%~dp0mobile"
where flutter >nul 2>nul || ( echo Flutter was not found. Open the "Flutter command prompt" or add Flutter's bin folder to PATH, then run this again. & pause & exit /b 1 )
if "%APP_URL%"=="" set APP_URL=https://tim-tim-app.onrender.com
if not exist android (
  call flutter create --platforms=android --org app.timtim --project-name tim_tim _scaffold || ( pause & exit /b 1 )
  xcopy /e /i /y "_scaffold\android" "android" >nul
  rmdir /s /q _scaffold
)
py -3 tools\prepare_android.py 2>nul || python tools\prepare_android.py
call flutter pub get || ( pause & exit /b 1 )
call dart run flutter_launcher_icons
call flutter build apk --release --dart-define=APP_URL=%APP_URL% || ( echo. & echo BUILD FAILED. Copy the last 30 lines above and send them to your developer. & pause & exit /b 1 )
if not exist "..\release" mkdir "..\release"
copy /y "build\app\outputs\flutter-apk\app-release.apk" "..\release\Tim-Tim.apk" >nul
echo.
echo DONE. Your Android app is release\Tim-Tim.apk  (copy it to a phone and open it; allow "install unknown apps" once).
pause
