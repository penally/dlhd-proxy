#!/bin/bash
# DLHD Proxy Frontend Deployment Script

echo "🚀 DLHD Proxy Frontend Deployment"
echo "=================================="

# Build the frontend
echo "📦 Building frontend..."
python build_frontend.py build

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo "✅ Build completed successfully"

# Check which deployment method to use
if command -v wrangler &> /dev/null; then
    echo ""
    echo "🌐 Cloudflare Workers Deployment (Recommended)"
    echo "---------------------------------------------"
    echo "Command: wrangler pages deploy .web/build/client --project-name dlhd-proxy-frontend"
    echo ""
    echo "Or if you have wrangler.toml configured:"
    echo "Command: wrangler deploy"
    echo ""
    echo "Run one of the above commands to deploy to Cloudflare Workers/Pages"
else
    echo ""
    echo "⚠️  Wrangler CLI not found"
    echo "Install it first:"
    echo "npm install -g wrangler"
    echo "Then run:"
    echo "wrangler pages deploy .web/build/client --project-name dlhd-proxy-frontend"
fi

echo ""
echo "📋 Manual Deployment Steps:"
echo "1. Go to https://dash.cloudflare.com/"
echo "2. Navigate to Pages or Workers"
echo "3. Create new project/site"
echo "4. Upload the contents of .web/build/client/"
echo "5. Set build command to: python build_frontend.py build"
echo "6. Set build output directory to: .web/build/client"
