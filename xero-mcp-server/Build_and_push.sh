docker build --platform linux/amd64 -t us-central1-docker.pkg.dev/theta-window-344723/xero-mcp-server/xero-mcp-server:latest .

docker push us-central1-docker.pkg.dev/theta-window-344723/xero-mcp-server/xero-mcp-server:latest

# 3. Deploy to Cloud Run
gcloud run deploy xero-mcp-server \
  --image us-central1-docker.pkg.dev/theta-window-344723/xero-mcp-server/xero-mcp-server:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 3000 \
  --set-env-vars XERO_SCOPES="accounting.transactions accounting.contacts accounting.settings accounting.reports.read accounting.attachments" \
  --update-secrets MCP_API_KEY=MCP_API_KEY:latest,XERO_CLIENT_ID=XERO_CLIENT_ID:latest,XERO_CLIENT_SECRET=XERO_CLIENT_SECRET:latest,XERO_TENANT_ID=XERO_TENANT_ID:latest