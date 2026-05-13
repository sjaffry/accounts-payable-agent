/**
 * Xero MCP HTTP SSE Proxy
 *
 * Wraps @xeroapi/xero-mcp-server (stdio) as an HTTP SSE server that the
 * ADK MCPToolset can connect to via URL instead of spawning a local process.
 *
 * Design:
 *   - Each GET /sse connection fetches a fresh Xero client_credentials token,
 *     then spawns a dedicated xero-mcp-server subprocess with that token.
 *   - POST /messages?sessionId=<id> forwards JSON-RPC messages to the subprocess stdin.
 *   - Subprocess stdout is forwarded back as SSE data events.
 *   - When the SSE connection closes, the subprocess is killed.
 *
 * This per-connection spawn model ensures the token is always fresh (valid for
 * 30 minutes per Xero client_credentials grant) regardless of how long the
 * server has been running.
 *
 * Environment variables (required):
 *   XERO_CLIENT_ID      Xero Custom Connection client ID
 *   XERO_CLIENT_SECRET  Xero Custom Connection client secret
 *   XERO_TENANT_ID      Xero organisation/tenant ID
 *   MCP_API_KEY         Static API key required on every request (Authorization: Bearer <key>)
 *   XERO_SCOPES         (optional) space-separated accounting scopes
 *   PORT                (optional, default 3000)
 */

import { spawn } from "child_process";
import http from "http";
import { randomUUID } from "crypto";
import { fileURLToPath } from "url";
import { resolve, dirname } from "path";

const PORT = parseInt(process.env.PORT || "3000", 10);
const MCP_API_KEY = process.env.MCP_API_KEY || "";

/** Return true if the request carries a valid API key. */
function isAuthorized(req) {
  if (!MCP_API_KEY) return true; // no key configured — open (dev only)
  const header = req.headers["authorization"] || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  return token === MCP_API_KEY;
}
const XERO_TOKEN_URL = "https://identity.xero.com/connect/token";
const DEFAULT_SCOPES =
  "accounting.transactions accounting.contacts accounting.settings " +
  "accounting.reports.read accounting.attachments";

// Absolute path to the installed xero-mcp-server binary
const __dirname = dirname(fileURLToPath(import.meta.url));
const MCP_BIN = resolve(__dirname, "node_modules", ".bin", "xero-mcp-server");

/** Fetch a fresh access token using the client_credentials grant. */
async function fetchXeroToken() {
  const { XERO_CLIENT_ID, XERO_CLIENT_SECRET, XERO_SCOPES } = process.env;
  if (!XERO_CLIENT_ID || !XERO_CLIENT_SECRET) {
    throw new Error("XERO_CLIENT_ID and XERO_CLIENT_SECRET must be set");
  }
  const credentials = Buffer.from(
    `${XERO_CLIENT_ID}:${XERO_CLIENT_SECRET}`
  ).toString("base64");

  const response = await fetch(XERO_TOKEN_URL, {
    method: "POST",
    headers: {
      Authorization: `Basic ${credentials}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      scope: XERO_SCOPES || DEFAULT_SCOPES,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Xero token request failed ${response.status}: ${body}`);
  }
  const data = await response.json();
  return data.access_token;
}

// Active sessions: sessionId → { proc, sseRes }
const sessions = new Map();

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost`);

  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // ── Health check (unauthenticated — used by Cloud Run probes) ────────────
  if (url.pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", sessions: sessions.size }));
    return;
  }

  // ── API key check on all other routes ────────────────────────────────────
  if (!isAuthorized(req)) {
    res.writeHead(401, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Unauthorized" }));
    return;
  }

  // ── SSE endpoint ─────────────────────────────────────────────────────────
  if (url.pathname === "/sse" && req.method === "GET") {
    const sessionId = randomUUID();

    let token;
    try {
      token = await fetchXeroToken();
    } catch (err) {
      console.error("[xero-mcp] Failed to fetch Xero token:", err.message);
      res.writeHead(502, { "Content-Type": "text/plain" });
      res.end(`Xero authentication failed: ${err.message}`);
      return;
    }

    // Spawn a dedicated xero-mcp-server subprocess for this connection
    const proc = spawn(MCP_BIN, [], {
      env: {
        ...process.env,
        XERO_CLIENT_BEARER_TOKEN: token,
        XERO_TENANT_ID: process.env.XERO_TENANT_ID || "",
      },
      stdio: ["pipe", "pipe", "pipe"],
    });

    proc.on("error", (err) => {
      console.error(`[xero-mcp][${sessionId}] Subprocess error:`, err.message);
    });

    proc.stderr.on("data", (chunk) => {
      console.error(`[xero-mcp][${sessionId}]`, chunk.toString().trimEnd());
    });

    // Start SSE response
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    });

    // Tell the MCP client where to POST messages
    res.write(`event: endpoint\ndata: /messages?sessionId=${sessionId}\n\n`);

    sessions.set(sessionId, { proc, sseRes: res });
    console.log(`[xero-mcp] Session ${sessionId} opened`);

    // Forward subprocess stdout (newline-delimited JSON-RPC) as SSE data events
    let buffer = "";
    proc.stdout.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop(); // hold incomplete line
      for (const line of lines) {
        if (line.trim()) {
          res.write(`data: ${line}\n\n`);
        }
      }
    });

    proc.on("close", (code) => {
      console.log(
        `[xero-mcp] Session ${sessionId} subprocess exited (code ${code})`
      );
      sessions.delete(sessionId);
      try {
        res.end();
      } catch {}
    });

    req.on("close", () => {
      console.log(`[xero-mcp] Session ${sessionId} closed by client`);
      sessions.delete(sessionId);
      proc.kill();
    });

    return;
  }

  // ── Messages endpoint ─────────────────────────────────────────────────────
  if (url.pathname === "/messages" && req.method === "POST") {
    const sessionId = url.searchParams.get("sessionId");
    const session = sessions.get(sessionId);

    if (!session) {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("Session not found");
      return;
    }

    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      try {
        session.proc.stdin.write(body + "\n");
        res.writeHead(202);
        res.end();
      } catch (err) {
        res.writeHead(500, { "Content-Type": "text/plain" });
        res.end(`Failed to forward message: ${err.message}`);
      }
    });

    return;
  }

  res.writeHead(404);
  res.end("Not found");
});

server.listen(PORT, () => {
  console.log(`[xero-mcp] HTTP SSE proxy listening on port ${PORT}`);
  console.log(`[xero-mcp] SSE endpoint: http://localhost:${PORT}/sse`);
});
