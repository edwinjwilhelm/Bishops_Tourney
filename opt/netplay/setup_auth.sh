#!/bin/bash
# Setup script for Supabase Authentication Integration

echo "========================================="
echo "Bishops Game - Supabase Auth Setup"
echo "========================================="
echo ""

# Check if JWT secret is set
if [ -z "$SUPABASE_JWT_SECRET" ]; then
    echo "❌ SUPABASE_JWT_SECRET is not set!"
    echo ""
    echo "To set it:"
    echo "1. Go to: https://supabase.com/dashboard/project/wqceqyycatcjggmxunte/settings/api"
    echo "2. Find 'JWT Secret' section"
    echo "3. Copy the secret"
    echo "4. Run: export SUPABASE_JWT_SECRET='your-secret-here'"
    echo "5. Add to ~/.bashrc or ~/.zshrc to make permanent"
    echo ""
    read -p "Enter your JWT secret now (or press Enter to skip): " jwt_secret
    if [ -n "$jwt_secret" ]; then
        export SUPABASE_JWT_SECRET="$jwt_secret"
        echo "✅ JWT secret set for this session"
        echo "   Add this to your ~/.bashrc to make permanent:"
        echo "   export SUPABASE_JWT_SECRET='$jwt_secret'"
    else
        echo "⚠️  Skipping... Authentication will not work without JWT secret"
    fi
else
    echo "✅ SUPABASE_JWT_SECRET is set"
fi

echo ""
echo "Installing Python dependencies..."
pip install -r opt/netplay/netplay/requirements.txt

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Make sure JWT secret is set in environment"
echo "2. Start the server: python -m netplay.server_v3"
echo "3. Test authentication at: http://localhost:8200/static/index_v3.html"
echo ""
echo "See SUPABASE_AUTH_GUIDE.md for full documentation"
