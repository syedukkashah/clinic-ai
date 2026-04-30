import { jsxs, jsx } from "react/jsx-runtime";
import { useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useState } from "react";
import { Stethoscope, Sparkles, Activity, ShieldCheck } from "lucide-react";
import { u as useAuth, B as Button } from "./router-kWCNp4I7.js";
import { L as Label, I as Input } from "./label-Bp8Ivt_c.js";
import { toast } from "sonner";
import axios from "axios";
import "@tanstack/react-query";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-label";
function LoginPage() {
  const {
    login
  } = useAuth();
  const navigate = useNavigate();
  const role = "admin";
  const [email, setEmail] = useState("admin@mediflow.io");
  const [password, setPassword] = useState("demo");
  const [submitting, setSubmitting] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, role, password);
      navigate({
        to: "/dashboard"
      });
    } catch (err) {
      const description = axios.isAxiosError(err) ? err.response?.data?.detail ?? "Check your credentials and API connection." : "Check your credentials and API connection.";
      toast.error("Sign-in failed", {
        description
      });
    } finally {
      setSubmitting(false);
    }
  };
  return /* @__PURE__ */ jsxs("div", { className: "min-h-screen grid lg:grid-cols-2", children: [
    /* @__PURE__ */ jsxs("div", { className: "relative hidden lg:flex flex-col justify-between p-12 overflow-hidden", children: [
      /* @__PURE__ */ jsx("div", { className: "absolute inset-0 gradient-violet opacity-95" }),
      /* @__PURE__ */ jsx("div", { className: "absolute inset-0 opacity-30", style: {
        backgroundImage: "radial-gradient(circle at 20% 20%, white 1px, transparent 1px), radial-gradient(circle at 80% 60%, white 1px, transparent 1px)",
        backgroundSize: "60px 60px"
      } }),
      /* @__PURE__ */ jsxs("div", { className: "relative flex items-center gap-3 text-white", children: [
        /* @__PURE__ */ jsx("div", { className: "size-11 rounded-xl bg-white/15 backdrop-blur grid place-items-center", children: /* @__PURE__ */ jsx(Stethoscope, { className: "size-6" }) }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("div", { className: "font-display font-bold text-xl", children: "MediFlow" }),
          /* @__PURE__ */ jsx("div", { className: "text-xs opacity-80", children: "AI-Powered Clinic OS" })
        ] })
      ] }),
      /* @__PURE__ */ jsxs(motion.div, { initial: {
        opacity: 0,
        y: 20
      }, animate: {
        opacity: 1,
        y: 0
      }, className: "relative text-white space-y-6 max-w-md", children: [
        /* @__PURE__ */ jsx("h1", { className: "font-display font-bold text-4xl leading-tight", children: "Run your clinic with the intelligence of a thousand schedulers." }),
        /* @__PURE__ */ jsx("p", { className: "text-white/80 text-lg", children: "AI booking agents, predictive wait times, and real-time ops monitoring — all in one beautifully simple platform." }),
        /* @__PURE__ */ jsx("div", { className: "grid grid-cols-3 gap-3 pt-4", children: [{
          Icon: Sparkles,
          label: "AI Agents"
        }, {
          Icon: Activity,
          label: "Live Ops"
        }, {
          Icon: ShieldCheck,
          label: "HIPAA-ready"
        }].map(({
          Icon,
          label
        }) => /* @__PURE__ */ jsxs("div", { className: "rounded-xl bg-white/10 backdrop-blur p-4 text-center", children: [
          /* @__PURE__ */ jsx(Icon, { className: "size-5 mx-auto mb-2" }),
          /* @__PURE__ */ jsx("div", { className: "text-xs font-medium", children: label })
        ] }, label)) })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "relative text-white/60 text-xs", children: "© 2026 MediFlow Health Systems" })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "flex items-center justify-center p-6 sm:p-12", children: /* @__PURE__ */ jsxs(motion.form, { onSubmit: submit, initial: {
      opacity: 0,
      y: 12
    }, animate: {
      opacity: 1,
      y: 0
    }, className: "w-full max-w-md space-y-6", children: [
      /* @__PURE__ */ jsxs("div", { className: "lg:hidden flex items-center gap-3", children: [
        /* @__PURE__ */ jsx("div", { className: "size-10 rounded-xl gradient-primary grid place-items-center", children: /* @__PURE__ */ jsx(Stethoscope, { className: "size-5 text-white" }) }),
        /* @__PURE__ */ jsx("div", { className: "font-display font-bold text-lg", children: "MediFlow" })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h2", { className: "font-display font-bold text-3xl tracking-tight", children: "Welcome back" }),
        /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-1", children: "Sign in to your clinic dashboard" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
        /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
          /* @__PURE__ */ jsx(Label, { htmlFor: "email", children: "Email" }),
          /* @__PURE__ */ jsx(Input, { id: "email", type: "email", value: email, onChange: (e) => setEmail(e.target.value), required: true })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
          /* @__PURE__ */ jsx(Label, { htmlFor: "password", children: "Password" }),
          /* @__PURE__ */ jsx(Input, { id: "password", type: "password", value: password, onChange: (e) => setPassword(e.target.value), required: true })
        ] })
      ] }),
      /* @__PURE__ */ jsx(Button, { type: "submit", disabled: submitting, className: "w-full h-11 gradient-primary text-white border-0 shadow-glow hover:opacity-95", children: "Sign in to dashboard" }),
      /* @__PURE__ */ jsx("p", { className: "text-xs text-center text-muted-foreground", children: "Demo mode — use admin@mediflow.io / demo." })
    ] }) })
  ] });
}
export {
  LoginPage as component
};
