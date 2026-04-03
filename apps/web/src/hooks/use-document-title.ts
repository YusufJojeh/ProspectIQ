import { useEffect } from "react";
import { productName } from "@/lib/brand";

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = `${title} | ${productName}`;
  }, [title]);
}
