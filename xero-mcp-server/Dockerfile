FROM node:20-slim

WORKDIR /app

# Install dependencies (includes @xeroapi/xero-mcp-server binary)
COPY package.json ./
RUN npm install --omit=dev

COPY server.mjs ./

EXPOSE 3000

ENV PORT=3000

CMD ["node", "server.mjs"]
