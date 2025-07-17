# How to Create a Google Cloud Project for Memory Bank

## Step 1: Create Google Cloud Project

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Create a new project**:
   - Click "Select a project" dropdown at the top
   - Click "New Project"
   - Enter project name (e.g., "memory-bank-test")
   - Note the **Project ID** (will be auto-generated)
   - Click "Create"

## Step 2: Enable Required APIs

1. **Go to APIs & Services > Library**
2. **Enable these APIs**:
   - Vertex AI API
   - Cloud Resource Manager API
   - Cloud Storage API
   - Cloud Logging API

## Step 3: Set up Authentication

### Option A: Service Account (Recommended for production)
1. **Go to IAM & Admin > Service Accounts**
2. **Create Service Account**:
   - Name: "memory-bank-service"
   - Description: "Service account for Memory Bank testing"
3. **Grant Roles**:
   - `Vertex AI User` 
   - `Storage Object Admin`
   - `Logging Admin`
4. **Create Key**:
   - Click on created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose JSON format
   - Download the key file
5. **Set Environment Variable**:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/key.json"
   ```

### Option B: User Account (Easier for testing)
1. **Install Google Cloud CLI**: https://cloud.google.com/sdk/docs/install
2. **Authenticate**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud auth application-default login
   ```

## Step 4: Update Your .env File

```env
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_CLOUD_PROJECT=your-actual-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

## Step 5: Test Connection

Run this command to verify your setup:
```bash
gcloud auth application-default print-access-token
```

If you get a token, you're ready to use the full Memory Bank service!

## Regions Available for Memory Bank

- `us-central1` (recommended)
- `us-east1` 
- `us-west1`
- `europe-west1`
- `asia-southeast1`

## Cost Considerations

- **Free Tier**: Google Cloud offers $300 credit for new users
- **Memory Bank**: Currently in preview, pricing varies by usage
- **Vertex AI**: Pay per API call
- **Storage**: Minimal costs for memory storage

## Next Steps

Once you have a real project set up:
1. Update the `GOOGLE_CLOUD_PROJECT` in your `.env` file
2. Run `python memory_bank_test.py` to test full Vertex AI integration
3. Create agents with persistent memory across sessions

## Troubleshooting

- **"Project not found"**: Make sure project ID is correct
- **"Permission denied"**: Check IAM roles are assigned
- **"API not enabled"**: Enable required APIs in console
- **"Auth error"**: Run `gcloud auth application-default login`