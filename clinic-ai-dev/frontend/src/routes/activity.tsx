import { createFileRoute } from "@tanstack/react-router";
import { ActivityFeed } from "@/components/ActivityFeed";

export const Route = createFileRoute("/activity")({
  component: () => (
    <div className="space-y-6">
      <div>
        <h1 className="font-display font-bold text-3xl tracking-tight">Live Activity</h1>
        <p className="text-muted-foreground">
          Stream of every booking, AI action and system event.
        </p>
      </div>
      <div className="max-w-3xl">
        <ActivityFeed />
      </div>
    </div>
  ),
});
