import { WarningCircle } from "@phosphor-icons/react";

export default function ErrorNotice({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="error-notice" role="alert" aria-label="Call error"><WarningCircle size={21} /><p>{message}</p></div>;
}

