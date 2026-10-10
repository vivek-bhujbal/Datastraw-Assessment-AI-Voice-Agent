"use client";

import { ChatTeardropText, DownloadSimple } from "@phosphor-icons/react";
import { useEffect, useRef } from "react";
import type { Entry } from "@/types/call";

export function download(name: string, text: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Transcript({ entries, active }: { entries: Entry[]; active: boolean }) {
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => { if (list.current) list.current.scrollTop = list.current.scrollHeight; }, [entries]);
  return <section className="panel transcript-panel" id="conversation" aria-labelledby="transcript-title">
    <div className="panel-heading"><h2 id="transcript-title">Conversation</h2><button className="icon-button" aria-label="Download transcript" title="Download transcript" disabled={!entries.length} onClick={() => download("aura-transcript.json", JSON.stringify(entries, null, 2))}><DownloadSimple size={19} /></button></div>
    <p className="section-note">Your words and Aria’s played responses, in order.</p>
    <div className="transcript-list" ref={list} role="log" aria-live="polite" aria-relevant="additions">
      {!entries.length ? <div className="empty-transcript"><ChatTeardropText size={32} weight="light" /><h3>A little conversation goes a long way.</h3><p>{active ? "Your call is connecting. Messages will appear here as you talk." : "Start a call and your conversation will appear here."}</p></div>
        : entries.map((entry, index) => <div className={`message ${entry.speaker === "Customer" ? "customer" : "aria"}`} key={`${entry.turn_id}-${index}`}>
          <div className="message-meta"><strong>{entry.speaker}</strong><time dateTime={entry.timestamp}>{new Date(entry.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div>
          <p className={entry.playback === "interrupted" ? "interrupted" : ""}>{entry.text}</p>
        </div>)}
    </div>
    <div className="transcript-footer"><span>{entries.length} {entries.length === 1 ? "message" : "messages"}</span><span>{active ? "This call only" : "A fresh start with every call"}</span></div>
  </section>;
}

