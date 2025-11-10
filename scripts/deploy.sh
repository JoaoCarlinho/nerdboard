#!/bin/bash

# NerdBoard Deployment Script
# Automates Railway + AWS deployment setup

set -e  # Exit on error

echo "🚀 NerdBoard Deployment Setup"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI not found${NC}"
    echo "Install with: npm i -g @railway/cli"
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found${NC}"
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi

echo -e "${GREEN}✅ CLI tools verified${NC}"
echo ""

# Step 1: Railway Login
echo "Step 1: Railway Authentication"
echo "--------------------------------"
railway login
echo ""

# Step 2: Create Railway Project
echo "Step 2: Create Railway Project"
echo "--------------------------------"
read -p "Enter project name (default: nerdboard): " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-nerdboard}

railway init --name "$PROJECT_NAME"
echo -e "${GREEN}✅ Project created: $PROJECT_NAME${NC}"
echo ""

# Step 3: Add Databases
echo "Step 3: Add Databases"
echo "--------------------------------"
echo "Adding PostgreSQL..."
railway add --database postgresql
echo "Adding Redis..."
railway add --database redis
echo -e "${GREEN}✅ Databases added${NC}"
echo ""

# Step 4: Set Environment Variables
echo "Step 4: Set Environment Variables"
echo "--------------------------------"
read -p "Enter production API token (secure, 32+ chars): " API_TOKEN
read -p "Enter AWS S3 bucket name (default: nerdboard-ml-models): " S3_BUCKET
S3_BUCKET=${S3_BUCKET:-nerdboard-ml-models}
read -p "Enter AWS Access Key ID: " AWS_KEY
read -sp "Enter AWS Secret Access Key: " AWS_SECRET
echo ""
read -p "Enter AWS Region (default: us-east-1): " AWS_REGION
AWS_REGION=${AWS_REGION:-us-east-1}

echo ""
echo "Setting backend environment variables..."
railway variables set DEMO_TOKEN="$API_TOKEN" --service nerdboard-backend
railway variables set S3_MODEL_BUCKET="$S3_BUCKET" --service nerdboard-backend
railway variables set AWS_ACCESS_KEY_ID="$AWS_KEY" --service nerdboard-backend
railway variables set AWS_SECRET_ACCESS_KEY="$AWS_SECRET" --service nerdboard-backend
railway variables set AWS_REGION="$AWS_REGION" --service nerdboard-backend
railway variables set ENV=production --service nerdboard-backend
railway variables set DATABASE_URL='${{PostgreSQL.DATABASE_URL}}' --service nerdboard-backend
railway variables set REDIS_URL='${{Redis.REDIS_URL}}' --service nerdboard-backend

echo "Setting frontend environment variables..."
railway variables set VITE_API_TOKEN="$API_TOKEN" --service nerdboard-frontend
railway variables set NODE_ENV=production --service nerdboard-frontend
railway variables set VITE_API_URL='${{nerdboard-backend.RAILWAY_PUBLIC_URL}}' --service nerdboard-frontend

echo -e "${GREEN}✅ Environment variables set${NC}"
echo ""

# Step 5: Create AWS S3 Bucket
echo "Step 5: Create AWS S3 Bucket"
echo "--------------------------------"
aws s3 mb "s3://$S3_BUCKET" --region "$AWS_REGION" 2>/dev/null || echo "Bucket already exists"
aws s3api put-bucket-versioning --bucket "$S3_BUCKET" --versioning-configuration Status=Enabled
echo -e "${GREEN}✅ S3 bucket configured${NC}"
echo ""

# Step 6: Deploy Backend
echo "Step 6: Deploy Backend"
echo "--------------------------------"
cd nerdboard-backend
railway up --service nerdboard-backend --detach
cd ..
echo -e "${GREEN}✅ Backend deployment initiated${NC}"
echo ""

# Step 7: Deploy Frontend
echo "Step 7: Deploy Frontend"
echo "--------------------------------"
cd nerdboard-frontend
railway up --service nerdboard-frontend --detach
cd ..
echo -e "${GREEN}✅ Frontend deployment initiated${NC}"
echo ""

# Step 8: Wait and Check Health
echo "Step 8: Health Check"
echo "--------------------------------"
echo "Waiting 60 seconds for deployments..."
sleep 60

BACKEND_URL=$(railway status --service nerdboard-backend --json | jq -r '.deployments[0].url')
FRONTEND_URL=$(railway status --service nerdboard-frontend --json | jq -r '.deployments[0].url')

echo "Checking backend health..."
if curl -f "$BACKEND_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend health check pending...${NC}"
fi

echo "Checking frontend..."
if curl -f "$FRONTEND_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend loading...${NC}"
fi

echo ""
echo "================================"
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo "================================"
echo ""
echo "Backend URL:  $BACKEND_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""
echo "Next steps:"
echo "1. Run database migrations: railway run --service nerdboard-backend python -m app.scripts.run_migrations"
echo "2. Load demo data: railway run --service nerdboard-backend python -m app.scripts.load_demo --scenario physics_shortage"
echo "3. Train ML model: railway run --service nerdboard-backend python -m app.scripts.train_model"
echo "4. Set up GitHub Actions (add RAILWAY_TOKEN to GitHub secrets)"
echo ""
echo "Documentation: docs/CICD-SETUP.md"
