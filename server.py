import os
import httpx
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse

ROBO_BASE = os.getenv("ROBOMOTION_BASE_URL", "https://api.robomotion.io")
ROBO_TOKEN = os.getenv("ROBOMOTION_API_TOKEN", "")
SHARED_SECRET = os.getenv("MCP_SHARED_SECRET", "")

app = FastAPI(title="Robomotion MCP Connector")

def auth_ok(req: Request, key: str | None) -> bool:
    if not SHARED_SECRET:
        return True
    q = req.query_params.get("key")
    return key == SHARED_SECRET or q == SHARED_SECRET

async def robo(method: str, path: str, json=None, params=None):
    if not ROBO_TOKEN:
        raise HTTPException(500, "ROBOMOTION_API_TOKEN not set")
    headers = {"Authorization": f"Bearer {ROBO_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(method, f"{ROBO_BASE}{path}", headers=headers, json=json, params=params)
        try: data = r.json()
        except Exception: data = {"text": r.text}
        return {"status": r.status_code, "data": data}

TOOLS = [
    {"name": "auth_check", "description": "Verify Robomotion token works", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "flows_list", "description": "List Robomotion flows", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "flows_run", "description": "Run a Robomotion flow by ID", "inputSchema": {"type": "object", "properties": {"flowId": {"type": "string"}, "input": {"type": "object"}}, "required": ["flowId"]}},
    {"name": "jobs_list", "description": "List jobs", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "robots_list", "description": "List robots", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "webhook_trigger", "description": "Trigger a Robomotion webhook URL with payload", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "payload": {"type": "object"}}, "required": ["url"]}},
]

async def call_tool(name: str, args: dict):
    if name == "auth_check":
        return await robo("GET", "/v1/flows.list")
    if name == "flows_list":
        return await robo("GET", "/v1/flows.list")
    if name == "flows_run":
        return await robo("POST", "/v1/flows.run", json={"flowId": args["flowId"], "input": args.get("input", {})})
    if name == "jobs_list":
        return await robo("GET", "/v1/jobs.list")
    if name == "robots_list":
        return await robo("GET", "/v1/robots.list")
    if name == "webhook_trigger":
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(args["url"], json=args.get("payload", {}))
            return {"status": r.status_code, "data": r.text}
    raise HTTPException(404, f"Unknown tool: {name}")

@app.get("/health")
async def health(): return {"ok": True}

@app.post("/mcp")
async def mcp(request: Request, x_mcp_key: str | None = Header(default=None)):
    if not auth_ok(request, x_mcp_key):
        raise HTTPException(401, "Unauthorized")
    body = await request.json()
    method = body.get("method")
    rid = body.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "robomotion-mcp", "version": "1.0.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = body.get("params", {})
        out = await call_tool(params.get("name"), params.get("arguments", {}))
        return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": str(out)}]}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
