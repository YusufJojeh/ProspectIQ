import { useCallback, useState } from "react";

export interface ColumnVisibility {
  score: boolean;
  coverage: boolean;
  phone: boolean;
  website: boolean;
}

const STORAGE_KEY = "piq:leads_col_vis";

const DEFAULT: ColumnVisibility = {
  score: true,
  coverage: true,
  phone: false,
  website: true,
};

function readFromStorage(): ColumnVisibility {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT;
    const parsed = JSON.parse(raw) as Partial<ColumnVisibility>;
    return { ...DEFAULT, ...parsed };
  } catch {
    return DEFAULT;
  }
}

export function useColumnVisibility(): [ColumnVisibility, (key: keyof ColumnVisibility, value: boolean) => void] {
  const [visibility, setVisibility] = useState<ColumnVisibility>(readFromStorage);

  const toggle = useCallback((key: keyof ColumnVisibility, value: boolean) => {
    setVisibility((prev) => {
      const next = { ...prev, [key]: value };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // localStorage unavailable
      }
      return next;
    });
  }, []);

  return [visibility, toggle];
}
