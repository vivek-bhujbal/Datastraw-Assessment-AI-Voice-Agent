"use client";

import { CheckCircle, Code, DownloadSimple, FileText } from "@phosphor-icons/react";
import type { Outcome } from "@/types/call";
import { download } from "./Transcript";

export default function CallSummary({ outcome, pending, fallback }: { outcome: Outcome | null; pending: boolean; fallback: boolean }) {
  return <section className="outcome-grid" id="summary">
    <div className="panel summary-panel"><div className="panel-heading"><h2>Call summary</h2><FileText size={20} /></div>
      {outcome ? <div className="summary-content">
        <span className="resolution"><CheckCircle size={15} />{outcome.resolution_status.replaceAll("_", " ")}</span>
        {fallback && <p className="fallback-label">Factual fallback · AI summary unavailable</p>}
        <p>{outcome.call_summary}</p>
        {!!outcome.actions_taken.length && <><h3>Recorded actions</h3><ul>{outcome.actions_taken.map((action, i) => <li key={i}>{action}</li>)}</ul></>}
        {!!outcome.unresolved_questions.length && <><h3>Still open</h3><ul>{outcome.unresolved_questions.map((question, i) => <li key={i}>{question}</li>)}</ul></>}
      </div> : <div className="summary-empty"><FileText size={27} weight="light" /><p>{pending ? "Preparing your call summary…" : "The details, without the note-taking."}</p><span>{pending ? "Your microphone and speakers have stopped." : "End your call to see a summary and any open questions."}</span></div>}
    </div>
    <div className="panel json-panel"><div className="panel-heading"><h2><Code size={19} />JSON outcome</h2><button className="icon-button" disabled={!outcome} aria-label="Download JSON outcome" title="Download JSON outcome" onClick={() => download("aura-outcome.json", JSON.stringify(outcome, null, 2))}><DownloadSimple size={19} /></button></div>
      {outcome ? <pre tabIndex={0} aria-label="Structured call outcome">{JSON.stringify(outcome, null, 2)}</pre> : <div className="json-empty"><span>{pending ? "Waiting for validated outcome…" : "No call outcome yet"}</span><p>The structured outcome will appear after your call.</p></div>}
    </div>
  </section>;
}

