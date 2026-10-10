export type State = "Idle" | "Connecting" | "Listening" | "Thinking" | "Speaking" | "Ended" | "Error";

export type Entry = {
  speaker: "Customer" | "Aria";
  text: string;
  timestamp: string;
  turn_id: string;
  playback?: "played" | "interrupted" | null;
};

export type Outcome = {
  customer_intent: string | null;
  intents: string[];
  order_id: string | null;
  order_ids: string[];
  resolution_status: "RESOLVED" | "UNRESOLVED" | "PARTIALLY_RESOLVED" | "NO_CONVERSATION";
  call_summary: string;
  actions_taken: string[];
  unresolved_questions: string[];
};

export type Order = {
  order_id: string;
  customer_name: string;
  products: string[];
  order_value: number;
  status: string;
  courier?: string;
  tracking_number?: string;
  delivery_note?: string;
  order_note?: string;
  cancellation: { eligible: boolean; reason: string };
};

export type ToolRecord = { name: string; result: Record<string, unknown> };

