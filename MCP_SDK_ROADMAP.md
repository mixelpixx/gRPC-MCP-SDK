# gRPC-MCP-SDK Feature Parity Roadmap
**Target:** Match the JS (`@modelcontextprotocol/sdk`) and Python (`mcp`) official SDKs  
**Current version:** 1.0.0  
**MCP spec targets:** `2024-11-05` and `2025-03-26`

---

## Honest Gap Assessment

Your SDK has solid bones: gRPC transport, auth, streaming tools, a bridge layer, and A2A extensions. But it's missing about 60% of what makes the official SDKs fully capable. The gaps fall into three buckets:

1. **Missing primitives** — Resources and Prompts don't exist yet (only stubs in the bridge)
2. **Broken tool schema** — Tools use a custom `Parameter` type instead of JSON Schema `inputSchema`. This breaks compatibility with every MCP client that validates schemas.
3. **No notification system** — MCP is bidirectional. Servers need to push `notifications/` to clients for list changes, resource updates, progress, and logs. Your bridge has none of this.

The gRPC-as-internal-transport approach is fine. The bridge is the right architectural choice. The bridge just needs to actually implement the spec.

---

## Phase 1 — Fix the Broken Foundation (Do This First)
*Without this, nothing else works correctly with standard MCP clients.*

### 1.1 — Tool `inputSchema` (JSON Schema)
**What's broken:** Tools expose a custom `Parameter[]` type. MCP clients expect proper JSON Schema.  
**Where:** `core/types.py`, `core/server.py`, `bridge.py`, `proto/mcp.proto`

Current (wrong):
```python
parameters: List[ToolParameter]  # custom type
```
Required (correct):
```python
input_schema: Dict[str, Any]  # {"type": "object", "properties": {...}, "required": [...]}
```

**Changes needed:**
- Replace `ToolParameter` with `input_schema: dict` on `ToolDefinition`
- Update `@mcp_tool` decorator to accept `input_schema=` kwarg
- Update proto: replace `repeated Parameter parameters` with a JSON string field for the schema
- Update bridge `_handle_tools_list` to emit `inputSchema` correctly
- Keep backward compat: auto-convert old `parameters` list to JSON Schema during migration

### 1.2 — Structured Capabilities Negotiation
**What's broken:** Capabilities are `map<string, string>` (e.g., `"tools": "true"`). Spec requires structured objects.  
**Where:** `core/server.py` Initialize handler, `bridge.py` `_handle_initialize`

Required format:
```json
{
  "tools": { "listChanged": true },
  "resources": { "subscribe": true, "listChanged": true },
  "prompts": { "listChanged": true },
  "logging": {},
  "experimental": {}
}
```

**Changes needed:**
- Replace string map capabilities with a `Capabilities` dataclass
- Update proto to use a nested message or JSON field
- Update bridge initialize handler to emit spec-compliant capabilities
- Parse and store client capabilities during handshake

### 1.3 — `isError` on Tool Results
**What's broken:** `ToolResult` has no `isError` flag. Spec requires tools to be able to return errors as content (not RPC errors).  
**Where:** `core/types.py`, `proto/mcp.proto`

Add `is_error: bool = False` to `MCPToolResult` and the proto `ToolResult` message. The `add_error()` method should set this automatically.

### 1.4 — Image Content Type
**What's broken:** Content types are `text`, `json`, `binary`. MCP spec defines `text`, `image`, and `resource` (embedded).  
**Where:** `core/types.py`, `proto/mcp.proto`, `core/server.py`

Add to `MCPToolResult`:
```python
def add_image(self, data: bytes, mime_type: str) -> "MCPToolResult":
    # base64-encode, emit as {"type": "image", "data": "...", "mimeType": "..."}
```

Also add `EmbeddedResource` content type for tools that return resource references.

---

## Phase 2 — Resources (Largest Missing Primitive)
*The Python and JS SDKs treat resources as a first-class feature. You have empty stubs.*

### 2.1 — Resource Registry
Create `core/resource_registry.py` mirroring `ToolRegistry`. Needs:
- `@mcp_resource(uri="...", name="...", mime_type="...")` decorator
- `@mcp_resource_template(uri_template="file:///{path}")` for dynamic resources
- `ResourceDefinition` dataclass with: `uri`, `name`, `description`, `mime_type`
- `list_resources()` and `read_resource(uri)` methods

### 2.2 — Proto Extensions
Add to `mcp.proto`:
```protobuf
service MCPService {
  rpc ListResources(ListResourcesRequest) returns (ListResourcesResponse);
  rpc ReadResource(ReadResourceRequest) returns (ReadResourceResponse);
  rpc SubscribeResource(SubscribeRequest) returns (stream ResourceUpdate);
  rpc ListResourceTemplates(ListResourceTemplatesRequest) returns (ListResourceTemplatesResponse);
}
```

Resource content types to support: `TextResourceContents`, `BlobResourceContents`.

### 2.3 — Bridge Resource Handlers
Replace the stub `_handle_resources_list` / `_handle_resources_read` in `bridge.py` with real implementations that proxy to gRPC.

### 2.4 — Resource Subscriptions
When a client calls `resources/subscribe`, start a gRPC stream. When the resource changes, send `notifications/resources/updated` to the client over SSE. This requires a notification queue per SSE session (see Phase 3).

---

## Phase 3 — Notification System
*MCP is bidirectional. The bridge currently only does request/response. Servers need to push.*

### 3.1 — SSE Notification Queue Per Session
**Where:** `bridge.py`

Current SSE implementation only works for streaming tool results (one-shot sessions). You need a persistent SSE channel per client that can receive server-initiated notifications at any time.

Rewrite session management:
```python
class MCPSession:
    session_id: str
    notification_queue: asyncio.Queue
    active: bool
```

The `GET /mcp` SSE endpoint (per MCP 2025-03-26 spec) should open a persistent channel that the server can push to.

### 3.2 — Required Notification Types
| Notification | Trigger |
|---|---|
| `notifications/initialized` | After client sends `initialize` |
| `notifications/tools/list_changed` | When tools are registered/removed at runtime |
| `notifications/resources/list_changed` | When resource list changes |
| `notifications/resources/updated` | When a subscribed resource changes |
| `notifications/prompts/list_changed` | When prompt list changes |
| `notifications/progress` | During long-running operations (replaces current gRPC-only progress) |
| `notifications/message` | Server log messages (logging feature) |
| `notifications/cancelled` | Request cancellation |

### 3.3 — Progress Tokens
**What's broken:** Current streaming progress is gRPC-specific. Standard MCP uses `_meta.progressToken` in request params, and the server sends `notifications/progress` over the notification channel.

Clients that don't use gRPC streaming will never see progress. Fix: read `progressToken` from request meta, emit standard progress notifications via the session queue.

---

## Phase 4 — Prompts
*Prompts are the second missing core primitive.*

### 4.1 — Prompt Registry
Create `core/prompt_registry.py`:
- `@mcp_prompt(name="...", description="...")` decorator
- `PromptDefinition` with: `name`, `description`, `arguments: List[PromptArgument]`
- `PromptArgument`: `name`, `description`, `required`
- `list_prompts()` and `get_prompt(name, arguments)` methods

### 4.2 — Proto Extensions
```protobuf
rpc ListPrompts(ListPromptsRequest) returns (ListPromptsResponse);
rpc GetPrompt(GetPromptRequest) returns (GetPromptResponse);
```

`GetPromptResponse` contains `description` and `messages: List[PromptMessage]`.  
`PromptMessage` has `role` (user/assistant) and `content` (text, image, or embedded resource).

### 4.3 — Bridge Handlers
Add `prompts/list` and `prompts/get` to the bridge method router.

---

## Phase 5 — Sampling (Server → Client LLM Calls)
*This is what lets your MCP server ask the LLM to do something — a key differentiator vs. just tools.*

### 5.1 — Sampling Request from Server
The server calls `sampling/createMessage` on the **client** (reverse direction). This requires the bridge to forward the request from gRPC server → SSE client.

Add to bridge:
```python
async def request_sampling(self, session_id: str, messages: list, model_prefs: dict) -> dict:
    # Send sampling/createMessage request to client over SSE
    # Wait for client response (need a response future map)
    # Return result to gRPC server
```

### 5.2 — Proto Additions
```protobuf
rpc RequestSampling(SamplingRequest) returns (SamplingResponse);
```

The gRPC server calls this when a tool needs to sample from the LLM. The bridge intercepts and routes to the connected client.

---

## Phase 6 — Pagination
*All `list` operations need cursor-based pagination to match spec.*

### 6.1 — Cursor Pagination
Add to all list responses: `nextCursor: Optional[str]`  
Add to all list requests: `cursor: Optional[str]`

Affects: `tools/list`, `resources/list`, `prompts/list`, `resources/templates/list`

Implement in both the proto layer and the bridge handlers.

---

## Phase 7 — Tool Annotations
*New in MCP `2024-11-05`. Clients use these to decide how to present/confirm tool calls.*

Add `annotations` field to `ToolDefinition`:
```python
@dataclass
class ToolAnnotations:
    title: Optional[str] = None
    read_only_hint: bool = False       # tool doesn't modify state
    destructive_hint: bool = True      # tool may cause irreversible changes
    idempotent_hint: bool = False      # safe to call multiple times with same args
    open_world_hint: bool = True       # tool interacts with external world
```

Update `@mcp_tool` decorator, proto, and bridge serialization.

---

## Phase 8 — Stdio Transport
*Required if you want servers to work with Claude Desktop and most local MCP clients.*

The official SDKs have a `StdioServerTransport` that reads JSON-RPC from stdin and writes to stdout. Your SDK has no stdio support at all.

Create `transport/stdio.py`:
```python
class StdioTransport:
    async def run(self, handler: MCPServicer):
        # Read newline-delimited JSON-RPC from stdin
        # Write responses to stdout
        # Route notifications to stdout as well
```

This can reuse most of the bridge's JSON-RPC routing logic — extract that into a shared `JSONRPCRouter` class that both the HTTP bridge and stdio transport use.

---

## Phase 9 — Completion (Argument Autocomplete)
*Nice to have. Clients like Claude Desktop use this for tab-completion in tool/prompt args.*

Add `completion/complete` method:
- Request: `ref` (tool or prompt name + argument name) + `argument.value` (partial value)
- Response: `completion.values[]`, `completion.hasMore`, `completion.total`

Add `@mcp_completer(tool="my_tool", argument="status")` decorator for registering completers.

---

## Phase 10 — Elicitation (2025-03-26)
*Brand new. Servers can ask the client/user for additional input mid-execution.*

Add `elicitation/create` support:
```python
async def elicit(self, message: str, schema: dict) -> dict:
    # Server sends this to client during tool execution
    # Client presents UI to user and returns structured response
```

This is the most complex feature as it requires suspending tool execution while waiting for user input.

---

## Implementation Priority Order

| Priority | Phase | Effort | Impact |
|---|---|---|---|
| 🔴 Must-do first | 1.1 Tool inputSchema | Medium | Breaks all schema-validating clients |
| 🔴 Must-do first | 1.2 Capabilities | Small | Wrong handshake with every client |
| 🔴 Must-do first | 1.3 isError | Tiny | Required by spec |
| 🟠 Phase 2 | Resources | Large | Second core primitive |
| 🟠 Phase 3 | Notifications + SSE rewrite | Large | Needed by resources + progress |
| 🟠 Phase 4 | Prompts | Medium | Third core primitive |
| 🟡 Phase 6 | Pagination | Small | Needed for large tool/resource lists |
| 🟡 Phase 7 | Tool Annotations | Small | Client UX improvement |
| 🟡 Phase 8 | Stdio Transport | Medium | Claude Desktop + local client compat |
| 🟢 Phase 5 | Sampling | Large | Advanced agentic use case |
| 🟢 Phase 9 | Completion | Medium | Nice UX but not required |
| 🟢 Phase 10 | Elicitation | Large | Bleeding edge, spec still fresh |

---

## Structural Changes Required

Beyond feature additions, two architectural changes are needed:

**1. Extract a shared JSON-RPC router**  
`bridge.py` is doing too much. The method routing logic (`initialize`, `tools/list`, etc.) needs to be in a shared `JSONRPCHandler` class so stdio transport and HTTP bridge share the same implementation without duplication.

**2. Rewrite SSE session management**  
Current SSE is one-shot (one session per streaming tool call). You need persistent sessions with a notification queue. Clients connect once and receive all notifications for the lifetime of the session. This is a prerequisite for Resources subscriptions, progress tokens, and logging notifications.

---

## What the JS/Python SDKs Have That You Don't (Summary)

| Feature | JS SDK | Python SDK | Your SDK |
|---|---|---|---|
| Tools (list/call) | ✅ | ✅ | ✅ |
| Tool JSON Schema inputSchema | ✅ | ✅ | ❌ (custom type) |
| Tool annotations | ✅ | ✅ | ❌ |
| Tool isError | ✅ | ✅ | ❌ |
| Resources (list/read) | ✅ | ✅ | ❌ (stub only) |
| Resource templates | ✅ | ✅ | ❌ |
| Resource subscriptions | ✅ | ✅ | ❌ |
| Prompts (list/get) | ✅ | ✅ | ❌ |
| Sampling | ✅ | ✅ | ❌ |
| Roots | ✅ | ✅ | ❌ |
| Notifications (all types) | ✅ | ✅ | ❌ |
| Progress tokens | ✅ | ✅ | ❌ (gRPC-only) |
| Logging notifications | ✅ | ✅ | ❌ |
| Pagination (cursors) | ✅ | ✅ | ❌ |
| Stdio transport | ✅ | ✅ | ❌ |
| Streamable HTTP (2025-03-26) | ✅ | ✅ | Partial (SSE only) |
| Image content type | ✅ | ✅ | ❌ |
| Embedded resource content | ✅ | ✅ | ❌ |
| Completion/autocomplete | ✅ | ✅ | ❌ |
| Elicitation (2025) | ✅ | Partial | ❌ |
| Auth (JWT/API key) | ❌ | ❌ | ✅ (your advantage) |
| gRPC transport (performance) | ❌ | ❌ | ✅ (your advantage) |
| A2A extensions | ❌ | ❌ | ✅ (your advantage) |
| Rate limiting | ❌ | ❌ | ✅ (your advantage) |
