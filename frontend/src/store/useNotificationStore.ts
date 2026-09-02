/**
 * Notification store — themed toasts.
 *
 * GYPSI has no push channel (no WebSockets), so notifications are DERIVED
 * client-side by diffing polling results (see the notifier in the polish task).
 * This store only holds and presents them — it never fabricates business data.
 */

import { create } from "zustand";

export type NotificationKind =
  | "trade_approved"
  | "trade_rejected"
  | "position_closed"
  | "risk_threshold"
  | "market_session"
  | "agent_attention";

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  title: string;
  message: string;
  createdAt: number;
  read: boolean;
}

interface NotificationState {
  notifications: AppNotification[];
  /** Add a notification; returns its id. */
  push: (n: Omit<AppNotification, "id" | "createdAt" | "read">) => string;
  dismiss: (id: string) => void;
  dismissAll: () => void;
  markRead: (id: string) => void;
}

let counter = 0;

export const useNotificationStore = create<NotificationState>()((set) => ({
  notifications: [],
  push: (n) => {
    const id = `notif-${Date.now()}-${counter++}`;
    set((state) => ({
      notifications: [
        { ...n, id, createdAt: Date.now(), read: false },
        ...state.notifications,
      ].slice(0, 50),
    }));
    return id;
  },
  dismiss: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
  dismissAll: () => set({ notifications: [] }),
  markRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n,
      ),
    })),
}));

/** Toast auto-dismiss default. */
export const TOAST_DURATION_MS = 6000;
