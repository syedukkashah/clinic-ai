import { mlflowApi } from "@/api/mlflowApi";
import DataTable from "../shared/DataTable";
import MiniChart from "../shared/MiniChart";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray, fmtDate } from "./ViewHelpers";

export default function MLflowRegistryView() {
  const models = useAdminResource(() => mlflowApi.listRegisteredModels(), []);
  const experiments = useAdminResource(() => mlflowApi.listExperiments(), []);
  const modelRows = asArray(models.data?.registered_models || models.data);
  const experimentRows = asArray(experiments.data?.experiments || experiments.data);

  return (
    <div className="admin-view">
      <ViewHeader title="MLflow Registry" kicker="MLOps / Model Lifecycle" />
      {!models.ok && !models.loading && <ComingSoon endpoint="MLflow /api/2.0/mlflow/registered-models/list" />}
      <div className="admin-grid admin-grid--split">
        {(modelRows.length ? modelRows : [{ name: "wait_time_model" }, { name: "patient_load_model" }]).map((model) => (
          <Panel key={model.name} title={model.name}>
            <div className="admin-lifecycle">
              {["None", "Staging", "Production", "Archived"].map((stage) => (
                <span key={stage} className={stage === "Production" ? "is-filled" : ""}>{stage}</span>
              ))}
            </div>
          </Panel>
        ))}
      </div>
      <Panel title="Training Runs">
        <DataTable
          rows={experimentRows}
          columns={[
            { key: "experiment_id", label: "Run ID", render: (row) => <code>{row.experiment_id || row.run_id || "--"}</code> },
            { key: "name", label: "Name" },
            { key: "status", label: "Status", render: (row) => <FieldPill tone="green">{row.lifecycle_stage || row.status || "active"}</FieldPill> },
            { key: "start_time", label: "Start Time", render: (row) => fmtDate(row.start_time) },
          ]}
        />
      </Panel>
      <Panel title="Metric Trends">
        <MiniChart type="line" height={220} />
      </Panel>
    </div>
  );
}
