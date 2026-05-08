import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Appointment, AppointmentStatus } from "@/lib/mockData";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Search, Filter, Calendar, X, Repeat2 } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listAppointments,
  updateAppointment as apiUpdateAppointment,
} from "@/services/appointmentsService";
import { listDoctors } from "@/services/doctorsService";

export const Route = createFileRoute("/appointments")({
  component: AppointmentsPage,
});

const STATUS_STYLES: Record<AppointmentStatus, string> = {
  Confirmed: "bg-info/15 text-info border-info/30",
  Waiting: "bg-warning/15 text-warning border-warning/30",
  "In Progress": "bg-primary/15 text-primary border-primary/30",
  Completed: "bg-success/15 text-success border-success/30",
  Cancelled: "bg-destructive/15 text-destructive border-destructive/30",
};

function AppointmentsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const limit = 50;

  const [q, setQ] = useState("");
  const [doctor, setDoctor] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [editing, setEditing] = useState<Appointment | null>(null);

  // Reset to first page when search or filters change
  const handleFilterChange = (type: 'q' | 'doctor' | 'status', val: string) => {
    if (type === 'q') setQ(val);
    if (type === 'doctor') setDoctor(val);
    if (type === 'status') setStatus(val);
    setPage(0);
  };

  const { data: paginatedData, isLoading, isError } = useQuery({
    queryKey: ["appointments", page, q, doctor, status],
    queryFn: () => listAppointments({ 
      limit, 
      offset: page * limit, 
      search: q, 
      doctor_id: doctor, 
      status 
    }),
  });

  const { data: doctors = [] } = useQuery({ queryKey: ["doctors"], queryFn: listDoctors });
  const updateMut = useMutation({
    mutationFn: (params: { id: string; patch: Partial<Appointment> }) =>
      apiUpdateAppointment(params.id, params.patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="size-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        <p className="text-muted-foreground animate-pulse">Loading appointments...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-8 text-center">
        <div className="bg-destructive/10 text-destructive p-4 rounded-xl inline-block mb-4 border border-destructive/20">
          Failed to load appointments. Please check your connection.
        </div>
        <br />
        <Button onClick={() => window.location.reload()} variant="outline">Retry</Button>
      </div>
    );
  }

  const appointments = paginatedData?.items ?? [];
  const total = paginatedData?.total ?? 0;

  const cancel = (id: string) => {
    updateMut.mutate({ id, patch: { status: "Cancelled" } });
    toast.error("Appointment cancelled", {
      description: "Patient will be notified via SMS & WhatsApp.",
    });
  };

  const reassign = (id: string) => {
    const apt = appointments.find((a) => a.id === id);
    if (!apt) return;
    const others = doctors.filter((d) => d.id !== apt.doctorId);
    const newDoc = others[Math.floor(Math.random() * others.length)];
    if (!newDoc) return;

    updateMut.mutate({ id, patch: { doctorId: newDoc.id, doctorName: newDoc.name } });
    toast.success("Patient reassigned", { description: `Now with ${newDoc.name}` });
  };

  const saveEdit = (apt: Appointment) => {
    updateMut.mutate({
      id: apt.id,
      patch: {
        patientName: apt.patientName,
        doctorId: apt.doctorId,
        doctorName: apt.doctorName,
        time: apt.time,
        status: apt.status,
      },
    });
    setEditing(null);
    toast.success("Appointment updated");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-3xl tracking-tight">Appointments</h1>
          <p className="text-muted-foreground">
            {total.toLocaleString()} total appointments found
          </p>
        </div>
      </div>

      <div className="rounded-2xl glass-card p-4">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search patient..."
              value={q}
              onChange={(e) => handleFilterChange('q', e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={doctor} onValueChange={(v) => handleFilterChange('doctor', v)}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Doctor" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All doctors</SelectItem>
              {doctors.map((d) => (
                <SelectItem key={d.id} value={String(d.id)}>
                  {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={(v) => handleFilterChange('status', v)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {(
                [
                  "Confirmed",
                  "Waiting",
                  "In Progress",
                  "Completed",
                  "Cancelled",
                ] as AppointmentStatus[]
              ).map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline">
            <Filter className="size-4 mr-2" />
            More filters
          </Button>
        </div>
      </div>

      <div className="rounded-2xl glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wider text-muted-foreground border-b border-border/60">
              <tr>
                <th className="text-left font-medium px-5 py-3">Patient</th>
                <th className="text-left font-medium px-5 py-3">Doctor</th>
                <th className="text-left font-medium px-5 py-3">Time</th>
                <th className="text-left font-medium px-5 py-3">Reason</th>
                <th className="text-left font-medium px-5 py-3">Wait (pred)</th>
                <th className="text-left font-medium px-5 py-3">Status</th>
                <th className="text-right font-medium px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence initial={false}>
                {appointments.map((a, i) => (
                  <motion.tr
                    key={a.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ delay: Math.min(i * 0.01, 0.3) }}
                    className="border-b border-border/40 hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="size-8 rounded-full gradient-violet grid place-items-center text-white text-xs font-semibold">
                          {a.patientName[0]}
                        </div>
                        <div>
                          <div className="font-medium">{a.patientName}</div>
                          <div className="text-xs text-muted-foreground">{a.patientId}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">{a.doctorName}</td>
                    <td className="px-5 py-3 font-medium">{a.time}</td>
                    <td className="px-5 py-3 text-muted-foreground">{a.reason}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`font-semibold ${a.predictedWaitMin > 30 ? "text-destructive" : a.predictedWaitMin > 15 ? "text-warning" : "text-success"}`}
                      >
                        {a.predictedWaitMin}m
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${STATUS_STYLES[a.status]}`}
                      >
                        {a.status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setEditing(a)}
                          title="Reschedule"
                        >
                          <Calendar className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => reassign(a.id)}
                          title="Reassign"
                        >
                          <Repeat2 className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => cancel(a.id)}
                          title="Cancel"
                        >
                          <X className="size-4" />
                        </Button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
        <div className="p-4 border-t border-border/40 flex items-center justify-between bg-muted/20">
          <div className="text-sm text-muted-foreground">
            Showing {page * limit + 1} to {Math.min((page + 1) * limit, total)} of {total.toLocaleString()}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => {
                setPage(p => p - 1);
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={(page + 1) * limit >= total}
              onClick={() => {
                setPage(p => p + 1);
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            >
              Next
            </Button>
          </div>
        </div>
      </div>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Reschedule appointment</DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label>Patient</Label>
                <Input
                  value={editing.patientName}
                  onChange={(e) => setEditing({ ...editing, patientName: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Time</Label>
                  <Input
                    type="time"
                    value={editing.time}
                    onChange={(e) => setEditing({ ...editing, time: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Status</Label>
                  <Select
                    value={editing.status}
                    onValueChange={(v) =>
                      setEditing({ ...editing, status: v as AppointmentStatus })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(
                        [
                          "Confirmed",
                          "Waiting",
                          "In Progress",
                          "Completed",
                          "Cancelled",
                        ] as AppointmentStatus[]
                      ).map((s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Doctor</Label>
                <Select
                  value={String(editing.doctorId)}
                  onValueChange={(v) =>
                    setEditing({
                      ...editing,
                      doctorId: Number(v),
                      doctorName: doctors.find((d) => String(d.id) === v)?.name ?? "",
                    })
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {doctors.map((d) => (
                      <SelectItem key={d.id} value={String(d.id)}>
                        {d.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="rounded-lg bg-info/10 text-info text-xs p-3">
                AI suggestion: 14:15 with {doctors[0]?.name ?? "Staff"} reduces predicted wait by 12
                min.
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button
              className="gradient-primary text-white border-0"
              onClick={() => editing && saveEdit(editing)}
            >
              Save changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
