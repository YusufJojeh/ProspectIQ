import { useEffect, useState } from "react";
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
      <CommandInput placeholder="Search leads, jobs, evidence, or run an action…" />
      <CommandList>
        <CommandEmpty>No results. Try a different query.</CommandEmpty>

        <CommandGroup heading="Quick actions">
          <CommandItem onSelect={() => go(appPaths.searches)}>
            <Plus className="size-4" />
            New search job
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.aiAnalysis)}>
            <Zap className="size-4" />
            Run AI analysis on current view
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.exports)}>
            <FileDown className="size-4" />
            Export selection to CSV
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Navigate">
          <CommandItem onSelect={() => go(appPaths.dashboard)}>
            <LayoutDashboard className="size-4" />
            Dashboard
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.searches)}>
            <Radar className="size-4" />
            Search Jobs
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.leads)}>
            <Users className="size-4" />
            Leads
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.aiAnalysis)}>
            <Sparkles className="size-4" />
            AI Analysis
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.outreach)}>
            <Send className="size-4" />
            Outreach Drafts
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.admin)}>
            <ShieldCheck className="size-4" />
            Admin
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.auditLogs)}>
            <ScrollText className="size-4" />
            Audit Logs
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.exports)}>
            <FileDown className="size-4" />
            Exports
          </CommandItem>
          <CommandItem onSelect={() => go(appPaths.settings)}>
            <Settings className="size-4" />
            Settings
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
