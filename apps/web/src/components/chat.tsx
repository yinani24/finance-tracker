"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import {
  Loader2,
  MessageSquare,
  Bot,
  ArrowRight,
  ArrowUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SUGGESTED_QUESTIONS = [
  "What's my net worth?",
  "How much did I spend last month?",
  "Spending by category",
  "Goal progress",
];

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

export function Chat() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [input, setInput] = useState("");

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: `${API_BASE}/chat`,
        headers: getAuthHeaders,
      }),
    []
  );

  const { messages, sendMessage, status } = useChat({ transport });

  const isLoading = status === "streaming" || status === "submitted";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    sendMessage({ text });
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  function sendSuggestion(question: string) {
    if (isLoading) return;
    sendMessage({ text: question });
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="bg-card rounded-2xl border border-border flex flex-col h-[460px]">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-xl bg-accent">
            <Bot className="w-4 h-4 text-card-foreground" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-card-foreground tracking-tight">
              Financial Assistant
            </h3>
          </div>
        </div>
        {hasMessages && (
          <span className="text-[11px] text-muted-foreground font-mono tracking-wide uppercase">
            {isLoading ? "Thinking..." : "Ready"}
          </span>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          <div className="flex flex-col justify-between h-full">
            {/* Empty state — left-aligned, wide-friendly */}
            <div className="px-6 pt-8">
              <div className="flex items-center gap-3 mb-3">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-accent">
                  <MessageSquare className="w-5 h-5 text-muted" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-card-foreground tracking-tight">
                    Ask about your finances
                  </h3>
                  <p className="text-sm text-muted-foreground leading-snug">
                    Accounts, transactions, spending, goals, and more
                  </p>
                </div>
              </div>
            </div>

            {/* Suggestions — horizontal chips at bottom */}
            <div className="px-6 pb-4">
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-2.5">
                Suggestions
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendSuggestion(q)}
                    className="group inline-flex items-center gap-1.5 text-sm px-3.5 py-2 rounded-xl border border-border text-muted hover:text-card-foreground hover:bg-accent active:scale-[0.98] transition-all"
                  >
                    <span>{q}</span>
                    <ArrowRight className="w-3 h-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="px-5 py-4 space-y-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "flex gap-3",
                  m.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {m.role === "assistant" && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-accent flex items-center justify-center mt-0.5">
                    <Bot className="w-3.5 h-3.5 text-card-foreground" />
                  </div>
                )}
                <div
                  className={cn(
                    "max-w-[70%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                    m.role === "user"
                      ? "bg-primary text-primary-foreground rounded-br-sm"
                      : "bg-accent text-card-foreground rounded-bl-sm"
                  )}
                >
                  {m.parts.map((part, i) => {
                    if (part.type === "text") {
                      return (
                        <span key={i} className="whitespace-pre-wrap">
                          {part.text}
                        </span>
                      );
                    }
                    return null;
                  })}
                </div>
              </div>
            ))}
            {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
              <div className="flex gap-3 justify-start">
                <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-accent flex items-center justify-center mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-card-foreground" />
                </div>
                <div className="bg-accent rounded-2xl rounded-bl-sm px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border px-4 py-3">
        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-3 bg-accent/50 rounded-xl px-4 py-2.5 focus-within:bg-accent motion-base"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your finances..."
            disabled={isLoading}
            rows={1}
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 resize-none max-h-[120px] py-0.5"
          />
          <Button
            type="submit"
            size="icon-sm"
            disabled={isLoading || !input.trim()}
            className="shrink-0 rounded-lg"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ArrowUp className="w-4 h-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}
