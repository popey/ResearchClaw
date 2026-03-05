import { useEffect, useRef, useState } from "react";
import { MessageCircle, X } from "lucide-react";
import { getConsolePushMessages } from "../api";
import type { PushMessage } from "../types";

const POLL_INTERVAL_MS = 2500;
const AUTO_DISMISS_MS = 8000;
const MAX_SEEN_IDS = 500;
const MAX_VISIBLE_BUBBLES = 4;
const MAX_NEW_PER_POLL = 2;
const TITLE_BLINK_PREFIX = "\u2022 ";

type BubbleItem = PushMessage & {
  dismissAt: number;
};

export default function ConsoleCronBubble() {
  const [items, setItems] = useState<BubbleItem[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const seenIdsRef = useRef<Set<string>>(new Set());
  const originalTitleRef = useRef(document.title);
  const blinkRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function dismiss(id: string) {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }

  useEffect(() => {
    originalTitleRef.current = document.title;
  }, []);

  useEffect(() => {
    const tick = () => {
      void getConsolePushMessages()
        .then((messages) => {
          if (!messages.length) return;
          const seen = seenIdsRef.current;
          if (seen.size > MAX_SEEN_IDS) seen.clear();
          const now = Date.now();
          const newItems: BubbleItem[] = [];
          for (const msg of messages) {
            if (seen.has(msg.id)) continue;
            seen.add(msg.id);
            newItems.push({ ...msg, dismissAt: now + AUTO_DISMISS_MS });
          }
          if (!newItems.length) return;
          const toAdd = newItems.slice(-MAX_NEW_PER_POLL);
          setItems((prev) => [...prev, ...toAdd].slice(-MAX_VISIBLE_BUBBLES));
        })
        .catch(() => {});
    };

    tick();
    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (!items.length) return;
    const timer = setInterval(() => {
      const now = Date.now();
      setItems((prev) => prev.filter((item) => item.dismissAt > now));
    }, 500);
    return () => clearInterval(timer);
  }, [items.length]);

  useEffect(() => {
    if (items.length === 0 || !document.hidden || blinkRef.current) return;
    const original = originalTitleRef.current;
    let showPrefix = true;
    blinkRef.current = setInterval(() => {
      document.title = showPrefix
        ? `${TITLE_BLINK_PREFIX}${original}`
        : original;
      showPrefix = !showPrefix;
    }, 800);
    return () => {
      if (blinkRef.current) {
        clearInterval(blinkRef.current);
        blinkRef.current = null;
      }
      document.title = original;
    };
  }, [items.length]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState !== "visible") return;
      if (blinkRef.current) {
        clearInterval(blinkRef.current);
        blinkRef.current = null;
      }
      document.title = originalTitleRef.current;
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  if (!items.length) return null;

  return (
    <div className="cron-bubble-wrap" role="region" aria-label="Cron messages">
      {items.map((item) => (
        <div key={item.id} className="cron-bubble-item">
          <MessageCircle size={18} className="cron-bubble-icon" />
          <p className="cron-bubble-text" title={item.text}>
            {item.text}
          </p>
          <button
            type="button"
            className="cron-bubble-close"
            onClick={() => dismiss(item.id)}
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
