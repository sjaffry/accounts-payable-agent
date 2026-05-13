
gcloud artifacts repositories create xero-mcp-server \
  --repository-format=docker \
  --location=us-central1

echo -n "$MCP_API_KEY" | gcloud secrets create MCP_API_KEY --project theta-window-344723 --data-file=- 2>/dev/null || \
  gcloud secrets versions add MCP_API_KEY --project theta-window-344723 --data-file=<(echo -n "$MCP_API_KEY")

echo -n "$XERO_CLIENT_ID" | gcloud secrets create XERO_CLIENT_ID --project theta-window-344723 --data-file=- 2>/dev/null || \
  gcloud secrets versions add XERO_CLIENT_ID --project theta-window-344723 --data-file=<(echo -n "$XERO_CLIENT_ID")

echo -n "$XERO_CLIENT_SECRET" | gcloud secrets create XERO_CLIENT_SECRET --project theta-window-344723 --data-file=- 2>/dev/null || \
  gcloud secrets versions add XERO_CLIENT_SECRET --project theta-window-344723 --data-file=<(echo -n "$XERO_CLIENT_SECRET")

echo -n "$XERO_TENANT_ID" | gcloud secrets create XERO_TENANT_ID --project theta-window-344723 --data-file=- 2>/dev/null || \
  gcloud secrets versions add XERO_TENANT_ID --project theta-window-344723 --data-file=<(echo -n "$XERO_TENANT_ID")
