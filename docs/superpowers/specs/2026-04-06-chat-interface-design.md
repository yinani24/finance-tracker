# Chat Interface Design Spec

**Date:** 2026-04-06
**Status:** Approved

## Overview

Add an AI chat interface to the dashboard using the Vercel AI SDK on the frontend and Anthropic Claude on the FastAPI backend. The chat is embedded in the dashboard page as the primary interaction surface, sitting below the existing stat cards. Claude has access to financial data via tool/function-calling that queries directly against the existing repositories.

## Architecture

```
Frontend (Next.js)                    Backend (FastAPI)
─────────────────                    ─────────────────
useChat() hook                       POST /chat (SSE stream)
    │                                    │
    ├── POST messages ──────────────► Anthropic SDK (streaming)
    │                                    │
    │                                    ├── tool calls ──► repositories
    │                                    │   get_accounts()    (AccountRepo)
    │                                    │   get_transactions() (TransactionRepo)
    │                                    │   get_goals()        (GoalRepo)
    │                                    │   get_cards()        (CardRepo)
    │                                    │   get_net_worth()    (AccountRepo)
    │                                    │   get_spending_by_category() (TransactionRepo)
    │                                    │
    ◄── SSE stream back ◄────────────    └── streamed text response
```

## Backend: FastAPI `/chat` Endpoint

### File: `app/api/chat.py`

- **Route:** `POST /chat`
- **Auth:** Same Supabase JWT auth via `get_current_user` dependency
- **Request body:** `{ messages: [{ role: "user"|"assistant", content: string }] }`
- **Response:** SSE stream (`text/event-stream`) in Vercel AI SDK compatible format

### Anthropic SDK Integration

- Use `anthropic` Python SDK with `client.messages.stream()`
- Model: `claude-sonnet-4-20250514` (fast, good at tool use)
- System prompt: financial assistant context with today's date
- Stream response using SSE format that Vercel AI SDK can consume:
  - `data: {"type":"text-delta","textDelta":"..."}\n\n` for text chunks
  - Standard AI SDK stream protocol

### Tools (defined server-side)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_accounts` | none | List all user accounts with balances |
| `get_transactions` | `category?: string, account_id?: int, limit?: int` | Query transactions with optional filters |
| `get_spending_by_category` | `months?: int` | Aggregate spending grouped by category |
| `get_net_worth` | none | Sum of all account balances |
| `get_goals` | none | List all financial goals with progress |
| `get_cards` | none | List credit cards |

Tools query the existing repositories directly (AccountRepository, TransactionRepository, etc.) — no HTTP calls needed.

### Tool execution flow

1. Claude decides to call a tool based on user question
2. FastAPI executes the tool function against the DB
3. Tool result is sent back to Claude
4. Claude generates a natural language response incorporating the data
5. Response is streamed to the frontend

### Config

Add `FT_ANTHROPIC_API_KEY` to `Settings` in `config.py`.

## Frontend: Dashboard Chat Component

### Dependencies

- `ai` (Vercel AI SDK) — `useChat` hook
- No additional UI libraries needed — use existing shadcn components + custom chat bubbles

### Dashboard Layout Change

The dashboard page (`app/(app)/dashboard/page.tsx`) keeps the stat cards grid at the top. Below it, add a chat interface that takes remaining vertical space.

```
┌──────────────────────────────────┐
│  Net Worth │ Income │ Expenses │ Goals  │  ← stat cards (existing)
├──────────────────────────────────┤
│                                  │
│  Chat messages (scrollable)      │  ← new
│  - assistant greeting            │
│  - user messages                 │
│  - assistant responses           │
│                                  │
├──────────────────────────────────┤
│  [  Type a message...    ] [Send]│  ← input bar
└──────────────────────────────────┘
```

### `useChat` Configuration

```ts
const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
  api: `${API_BASE}/chat`,
  headers: async () => getAuthHeaders(),
});
```

Point `api` at the FastAPI `/chat` endpoint. Pass auth headers so the backend can identify the user.

### Chat UI Components

All in `app/(app)/dashboard/page.tsx` or extracted to `components/chat.tsx` if it gets large:

- **Message list:** Scrollable container, auto-scrolls to bottom on new messages
- **User messages:** Right-aligned, subtle background
- **Assistant messages:** Left-aligned, card-foreground text, supports markdown (bold, lists, code for numbers)
- **Input bar:** Fixed at bottom of chat area, text input + send button, disabled while streaming
- **Loading indicator:** Subtle animated dots while assistant is responding
- **Initial state:** Show a greeting message from the assistant with suggested questions

### Styling

- Chat area uses `flex-1` to fill remaining dashboard height
- Messages use `font-sans` for text, `font-mono tabular-nums` for any financial figures
- Clean, minimal bubble design — no heavy borders or shadows
- Consistent with existing zinc dark / slate light palette

## Data Flow

1. User types a question → `useChat` POSTs to `{API_BASE}/chat`
2. FastAPI authenticates via JWT, loads user_id
3. FastAPI calls Anthropic API with messages + tool definitions
4. Claude may call tools → FastAPI executes against DB repos → feeds results back to Claude
5. Claude streams final response → FastAPI streams SSE to frontend
6. `useChat` hook updates React state incrementally as chunks arrive

## What's NOT in v1

- Chat history persistence (messages live in React state only)
- Multi-turn tool chains beyond what Claude handles natively
- File/image uploads
- Chat in pages other than dashboard

## SSE Stream Format

The FastAPI endpoint must output the Vercel AI SDK stream protocol. The simplest approach: use the `ai` npm package's expected format, which is newline-delimited JSON:

```
0:"Hello"
0:", how"
0:" can I help?"
```

Where `0:` prefix = text content. This is the AI SDK Data Stream format.
