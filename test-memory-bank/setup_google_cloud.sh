#!/bin/bash
# Setup script for Google Cloud and Memory Bank testing

echo "🚀 Setting up Google Cloud for Memory Bank"
echo "=========================================="

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "📦 Installing Google Cloud CLI..."
    
    # Install gcloud CLI
    curl -sSL https://sdk.cloud.google.com | bash
    
    # Add to PATH
    echo 'export PATH=$PATH:$HOME/google-cloud-sdk/bin' >> ~/.bashrc
    source ~/.bashrc
    
    echo "✅ Google Cloud CLI installed"
else
    echo "✅ Google Cloud CLI already installed"
fi

# Set project
echo "🔧 Setting up project gen-lang-client-0220754900..."
gcloud config set project gen-lang-client-0220754900

# Authenticate
echo "🔑 Starting authentication..."
echo "Please follow the prompts to authenticate with Google Cloud"
gcloud auth login
gcloud auth application-default login

# Enable required APIs
echo "🛠️ Enabling required APIs..."
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable logging.googleapis.com

# Test authentication
echo "🧪 Testing authentication..."
gcloud auth application-default print-access-token > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Authentication successful!"
else
    echo "❌ Authentication failed. Please run:"
    echo "  gcloud auth login"
    echo "  gcloud auth application-default login"
fi

echo "🎉 Setup complete! You can now run:"
echo "  python memory_bank_test.py"