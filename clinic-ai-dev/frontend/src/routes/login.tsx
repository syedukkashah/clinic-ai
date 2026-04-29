import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useState } from "react";
import { Stethoscope, Sparkles, ShieldCheck, Activity } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import axios from "axios";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const role = "admin" as const;
  const [email, setEmail] = useState("admin@mediflow.io");
  const [password, setPassword] = useState("demo");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, role, password);
      navigate({ to: "/dashboard" });
    } catch (err: unknown) {
      const description = axios.isAxiosError(err)
        ? (err.response?.data?.detail ?? "Check your credentials and API connection.")
        : "Check your credentials and API connection.";
      toast.error("Sign-in failed", { description });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left: brand panel */}
      <div className="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden">
        <div className="absolute inset-0 gradient-violet opacity-95" />
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, white 1px, transparent 1px), radial-gradient(circle at 80% 60%, white 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />

        <div className="relative flex items-center gap-3 text-white">
          <div className="size-11 rounded-xl bg-white/15 backdrop-blur grid place-items-center">
            <Stethoscope className="size-6" />
          </div>
          <div>
            <div className="font-display font-bold text-xl">MediFlow</div>
            <div className="text-xs opacity-80">AI-Powered Clinic OS</div>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative text-white space-y-6 max-w-md"
        >
          <h1 className="font-display font-bold text-4xl leading-tight">
            Run your clinic with the intelligence of a thousand schedulers.
          </h1>
          <p className="text-white/80 text-lg">
            AI booking agents, predictive wait times, and real-time ops monitoring — all in one
            beautifully simple platform.
          </p>

          <div className="grid grid-cols-3 gap-3 pt-4">
            {[
              { Icon: Sparkles, label: "AI Agents" },
              { Icon: Activity, label: "Live Ops" },
              { Icon: ShieldCheck, label: "HIPAA-ready" },
            ].map(({ Icon, label }) => (
              <div key={label} className="rounded-xl bg-white/10 backdrop-blur p-4 text-center">
                <Icon className="size-5 mx-auto mb-2" />
                <div className="text-xs font-medium">{label}</div>
              </div>
            ))}
          </div>
        </motion.div>

        <div className="relative text-white/60 text-xs">© 2026 MediFlow Health Systems</div>
      </div>

      {/* Right: form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <motion.form
          onSubmit={submit}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md space-y-6"
        >
          <div className="lg:hidden flex items-center gap-3">
            <div className="size-10 rounded-xl gradient-primary grid place-items-center">
              <Stethoscope className="size-5 text-white" />
            </div>
            <div className="font-display font-bold text-lg">MediFlow</div>
          </div>

          <div>
            <h2 className="font-display font-bold text-3xl tracking-tight">Welcome back</h2>
            <p className="text-muted-foreground mt-1">Sign in to your clinic dashboard</p>
          </div>

          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={submitting}
            className="w-full h-11 gradient-primary text-white border-0 shadow-glow hover:opacity-95"
          >
            Sign in to dashboard
          </Button>

          <p className="text-xs text-center text-muted-foreground">
            Demo mode — use admin@mediflow.io / demo.
          </p>
        </motion.form>
      </div>
    </div>
  );
}
