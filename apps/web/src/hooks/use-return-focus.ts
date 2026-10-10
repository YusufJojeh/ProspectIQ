import { useCallback, useEffect, useRef } from "react";

const INTERACTIVE = "button, a[href], [role='button'], [role='combobox'], input, select, textarea";

let lastActivated: HTMLElement | null = null;
let tracking = false;

/**
 * Touch and Safari-style pointers do not focus a button when it is tapped, so
 * `document.activeElement` cannot be trusted to identify what opened a dialog.
 * Track the last control that was activated instead, from the capture phase so it
 * is recorded before any handler opens the dialog.
 */
function trackActivation(): void {
  if (tracking || typeof document === "undefined") return;
  tracking = true;
  document.addEventListener(
    "click",
    (event) => {
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>(INTERACTIVE) : null;
      if (target) lastActivated = target;
    },
    true,
  );
}

/**
 * Controlled dialogs opened without a Radix Trigger lose their "return focus" target.
 * Remember what opened the dialog and hand it back through `onCloseAutoFocus`, which
 * Radix calls after unmounting, so it cannot race with the library's own focus handling.
 */
export function useReturnFocus(open: boolean): { onCloseAutoFocus: (event: Event) => void } {
  const origin = useRef<HTMLElement | null>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    trackActivation();
  }, []);

  useEffect(() => {
    if (open && !wasOpen.current) {
      const active = document.activeElement;
      const focused = active instanceof HTMLElement && active !== document.body ? active : null;
      origin.current = focused ?? lastActivated;
    }
    wasOpen.current = open;
  }, [open]);

  const onCloseAutoFocus = useCallback((event: Event) => {
    const target = origin.current;
    origin.current = null;
    if (target?.isConnected) {
      event.preventDefault();
      target.focus();
    }
  }, []);

  return { onCloseAutoFocus };
}
