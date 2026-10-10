"use client";

import { ArrowUpRight, Headphones, Leaf, LockKey, ShieldCheck } from "@phosphor-icons/react";
import AgentState from "@/components/AgentState";
import CallControls from "@/components/CallControls";
import CallSummary from "@/components/CallSummary";
import ErrorNotice from "@/components/ErrorNotice";
import SampleOrders from "@/components/SampleOrders";
import Transcript from "@/components/Transcript";
import { useCall } from "@/hooks/useCall";

export default function Home() {
  const call = useCall();
  return <>
    <header className="site-header"><div className="header-inner">
      <a className="brand" href="#"><Leaf size={32} weight="light" /><span>aura<span className="brand-sub">SKINCARE</span></span></a>
      <nav aria-label="Main navigation"><a className="nav-current" href="#support">Voice support</a><a href="#orders">Sample orders</a><a href="#summary">Call outcome <ArrowUpRight size={13} /></a></nav>
      <span className="header-label"><Headphones size={16} />Customer care</span>
    </div></header>
    <main className="page-shell">
      <div className="page-intro"><p className="eyebrow">A little care, a conversation away</p><h1>Good skincare.<br className="mobile-break" /> Thoughtful support.</h1><p>Meet Aria. Ask about your order or our policies, just by talking.</p></div>
      <ErrorNotice message={call.error} />
      <div className="support-grid" id="support">
        <div className="main-column">
          <section className="voice-panel" aria-label="Voice call with Aria">
            <AgentState state={call.state} duration={call.duration} />
            <CallControls active={call.active} ending={call.ending} mic={call.mic} start={call.start} end={call.end} meter={call.meter} />
            <div className="voice-footnote"><ShieldCheck size={15} /><span>AI voice support in English. Allow your mic to begin.</span></div>
          </section>
          <Transcript entries={call.entries} active={call.active} />
        </div>
        <aside className="side-column">
          <SampleOrders />
          <section className="policy-note"><span className="note-icon"><Leaf size={22} /></span><div><h2>Here to help with the everyday.</h2><p>Shipping, returns, damaged items, cancellations, and cash on delivery.</p><span>Try “What’s your return policy?”</span></div></section>
        </aside>
      </div>
      <CallSummary outcome={call.outcome} pending={call.ending} fallback={call.fallback} />
      <div className="privacy-note"><LockKey size={15} /><p>Your microphone is released when the call ends. Audio is sent to our AI provider to process your conversation. This demo uses sample orders.</p></div>
    </main>
    <footer className="site-footer"><span>Aura Skincare</span><span>Made for a little more care.</span></footer>
  </>;
}

