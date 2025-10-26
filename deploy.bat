@echo off
REM DLHD Proxy Frontend Deployment Script for Windows

echo 🚀 DLHD Proxy Frontend Deployment
echo ==================================
echo.

REM Build the frontend
echo 📦 Building frontend...
python build_frontend.py build

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Build failed!
    pause
    exit /b 1
)

echo ✅ Build completed successfully
echo.

REM Check which deployment method to use
wrangler --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo 🌐 Cloudflare Workers Deployment (Recommended)
    echo ---------------------------------------------
    echo Command: wrangler pages deploy .web/build/client --project-name dlhd-proxy-frontend
    echo.
    echo Or if you have wrangler.toml configured:
    echo Command: wrangler deploy
    echo.
    echo Run one of the above commands to deploy to Cloudflare Workers/Pages
) else (
    echo ⚠️  Wrangler CLI not found
    echo Install it first:
    echo npm install -g wrangler
    echo Then run:
    echo wrangler pages deploy .web/build/client --project-name dlhd-proxy-frontend
)

echo.
echo 📋 Manual Deployment Steps:
echo 1. Go to https://dash.cloudflare.com/
echo 2. Navigate to Pages or Workers
echo 3. Create new project/site
echo 4. Upload the contents of .web/build/client/
echo 5. Set build command to: python build_frontend.py build
echo 6. Set build output directory to: .web/build/client

pause
