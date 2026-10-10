import { Headphones, SpinnerGap } from "@phosphor-icons/react";
import type { State } from "@/types/call";

const descriptions: Record<State, string> = {
  Idle: "Ready when you are",
  Connecting: "Connecting your call…",
  Listening: "I’m listening. What can I help with?",
  Thinking: "Finding the right answer…",
  Speaking: "Aria is speaking. Your mic is paused.",
  Ended: "Thanks for stopping by",
  Error: "Your call needs attention",
};

export default function AgentState({ state, duration }: { state: State; duration: number }) {
  const time = `${Math.floor(duration / 60).toString().padStart(2, "0")}:${(duration % 60).toString().padStart(2, "0")}`;
  return <div className="agent-body">
    <div className="call-meta"><span className={`state-tag state-${state.toLowerCase()}`} aria-live="polite">{["Connecting", "Thinking"].includes(state) && <SpinnerGap className="spinner" size={13} />}{state}</span><span className="timer" aria-label="Call duration">{time}</span></div>
    <div className="agent-avatar"><Headphones size={48} weight="light" /></div>
    <h2>Meet Aria</h2>
    <p className="agent-role">Your Aura Skincare support agent</p>
    <p className="agent-caption" aria-live="polite">{descriptions[state]}</p>
  </div>;
}

