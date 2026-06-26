import { Sun, Moon, Monitor } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/app/theme-provider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function ThemeSwitcher() {
  const { t } = useTranslation();
  const { theme, setTheme, resolvedTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="size-9 shrink-0"
          aria-label={t("theme.switch")}
        >
          {resolvedTheme === "dark" ? (
            <Moon className="size-4" />
          ) : (
            <Sun className="size-4" />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onClick={() => setTheme("light")}
          className="gap-2"
          aria-current={theme === "light" ? "true" : undefined}
        >
          <Sun className="size-4" />
          <span>{t("theme.light")}</span>
          {theme === "light" ? (
            <span className="ms-auto text-xs text-muted-foreground">✓</span>
          ) : null}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("dark")}
          className="gap-2"
          aria-current={theme === "dark" ? "true" : undefined}
        >
          <Moon className="size-4" />
          <span>{t("theme.dark")}</span>
          {theme === "dark" ? (
            <span className="ms-auto text-xs text-muted-foreground">✓</span>
          ) : null}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("system")}
          className="gap-2"
          aria-current={theme === "system" ? "true" : undefined}
        >
          <Monitor className="size-4" />
          <span>{t("theme.system")}</span>
          {theme === "system" ? (
            <span className="ms-auto text-xs text-muted-foreground">✓</span>
          ) : null}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
