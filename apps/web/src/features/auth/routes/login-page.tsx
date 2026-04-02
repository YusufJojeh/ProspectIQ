import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { login } from "@/features/auth/api";
import { useDocumentTitle } from "@/hooks/use-document-title";

const loginSchema = z.object({
  workspace: z.string().min(2),
  email: z.string().email(),
  password: z.string().min(8),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  useDocumentTitle("Sign In");
  const navigate = useNavigate();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      workspace: "ws_default",
      email: "admin@prospectiq.local",
      password: "ChangeMe123!",
    },
  });

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: () => navigate("/"),
  });

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.14),transparent_30%)]" />
      <Card className="relative w-full max-w-md overflow-hidden">
        <CardHeader>
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--muted)]">
            ProspectIQ
          </p>
          <CardTitle className="mt-2">Secure access to the workspace</CardTitle>
          <CardDescription>
            Sign in with the seeded workspace and admin account after running migrations and the seed script.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
            <div className="space-y-2">
              <label className="text-sm font-semibold">Workspace</label>
              <Input {...form.register("workspace")} />
              {form.formState.errors.workspace ? (
                <p className="text-sm text-red-600">{form.formState.errors.workspace.message}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold">Email</label>
              <Input {...form.register("email")} />
              {form.formState.errors.email ? (
                <p className="text-sm text-red-600">{form.formState.errors.email.message}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold">Password</label>
              <Input type="password" {...form.register("password")} />
              {form.formState.errors.password ? (
                <p className="text-sm text-red-600">{form.formState.errors.password.message}</p>
              ) : null}
            </div>

            {mutation.error ? <p className="text-sm text-red-600">{mutation.error.message}</p> : null}

            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
