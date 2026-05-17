docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/theta-window-344723/xero-mcp-server/ap-chat:latest .

docker push us-central1-docker.pkg.dev/theta-window-344723/xero-mcp-server/ap-chat:latest

gcloud run deploy ap-chat \
  --image us-central1-docker.pkg.dev/theta-window-344723/xero-mcp-server/ap-chat:latest \
  --region us-central1 \
  --project theta-window-344723 \
  --allow-unauthenticated \
  --port 8080