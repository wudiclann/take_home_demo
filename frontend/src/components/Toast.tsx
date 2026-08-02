import { useEffect, useState } from "react";

type ToastVariant = "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

let toasts: ToastItem[] = [];
let nextId = 0;
let listeners: ((items: ToastItem[]) => void)[] = [];

function emit() {
  for (const listener of listeners) listener(toasts);
}

export function showToast(message: string, variant: ToastVariant = "error") {
  const id = nextId++;
  toasts = [...toasts, { id, message, variant }];
  emit();
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    emit();
  }, 4000);
}

export default function ToastHost() {
  const [items, setItems] = useState<ToastItem[]>(toasts);

  useEffect(() => {
    listeners.push(setItems);
    return () => {
      listeners = listeners.filter((l) => l !== setItems);
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <div className="m-toast-host">
      {items.map((item) => (
        <div key={item.id} className={`m-toast m-toast-${item.variant}`}>
          {item.message}
        </div>
      ))}
    </div>
  );
}
