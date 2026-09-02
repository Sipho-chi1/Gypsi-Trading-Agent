/**
 * Hermes types.
 *
 * Backend contract PENDING. The UI is conversational and does NOT fabricate
 * responses. Until the backend Hermes endpoint exists, `hermesService` reports
 * an awaiting-backend state and the UI shows it instead of faking answers.
 */

export interface HermesMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string; // ISO
}

export type HermesConnectionState = "awaiting-backend" | "connected";
