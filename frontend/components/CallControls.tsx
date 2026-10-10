import { Microphone, Phone, PhoneDisconnect } from "@phosphor-icons/react";
import type { RefObject } from "react";

type Props = {
  active: boolean; ending: boolean; mic: string;
  start: () => void; end: () => void; meter: RefObject<HTMLMeterElement | null>;
};

export default function CallControls({ active, ending, mic, start, end, meter }: Props) {
  return <div className="call-controls">
    <div className="flex flex-wrap justify-center gap-3">
      <button className="button primary" onClick={start} disabled={active}><Phone size={18} weight="bold" />Start call</button>
      <button className="button secondary" onClick={end} disabled={!active || ending}><PhoneDisconnect size={18} />End call</button>
    </div>
    <div className="mic-info"><Microphone size={15} /><span>{mic}</span><meter ref={meter} min="0" max="1" value="0" aria-label="Microphone input level" /></div>
  </div>;
}

