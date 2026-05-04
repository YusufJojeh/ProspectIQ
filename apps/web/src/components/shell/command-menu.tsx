import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard,
  Radar,
  Users,
  Sparkles,
  Send,
  ShieldCheck,
  ScrollText,
  FileDown,
  Settings,
  Plus,
  Zap,
} from "lucide-react";
import { appPaths } from "@/app/paths";

export function CommandMenu() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  function go(path: string) {
    setOpen(false);
    navigate(path);
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder={t("command.placeholder")} />
      <CommandList>
        <CommandEmpty>{t("command.noResults")}</CommandEmpty>

        <CommandGroup heading={t("command.quickActions")}>
          <CommandItem onSelect={() => go(appPaths.searches)}>
            <Plus className="size-4" />
            {t("command.newSearchJob")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.aiAnalysis)}>
            <Zap className="size-4" />
            {t("command.runAiAnalysis")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.exports)}>
            <FileDown className="size-4" />
            {t("command.exportSelection")}
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading={t("command.navigate")}>
          <CommandItem onSelect={() => go(appPaths.dashboard)}>
            <LayoutDashboard className="size-4" />
            {t("nav.dashboard")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.searches)}>
            <Radar className="size-4" />
            {t("nav.searches")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.leads)}>
            <Users className="size-4" />
            {t("nav.leads")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.aiAnalysis)}>
            <Sparkles className="size-4" />
            {t("nav.aiAnalysis")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.outreach)}>
            <Send className="size-4" />
            {t("nav.outreach")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.admin)}>
            <ShieldCheck className="size-4" />
            {t("nav.admin")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.auditLogs)}>
            <ScrollText className="size-4" />
            {t("nav.auditLogs")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.exports)}>
            <FileDown className="size-4" />
            {t("nav.exports")}
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.settings)}>
            <Settings className="size-4" />
            {t("nav.settings")}
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
