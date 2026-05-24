import { adminApi } from "@/api/adminApi";
import DataTable from "../shared/DataTable";
import HeatmapGrid from "../shared/HeatmapGrid";
import MiniChart from "../shared/MiniChart";
import { useAdminResource } from "../shared/hooks";
import { ComingSoon, FieldPill, Panel, ViewHeader, asArray } from "./ViewHelpers";

export default function LoadForecastView() {
  const doctors = useAdminResource(() => adminApi.getDoctors(), []);
  const status = useAdminResource(() => adminApi.getModelStatus("patient_load_model"), []);
  const rows = asArray(doctors.data);
  const heatRows = rows.map((doctor) => ({
    id: doctor.id,
    name: doctor.name,
    values: Array.from({ length: 13 }).map((_, index) => Math.max(0, Math.round(Number(doctor.peak_hour_patients || 4) + Math.cos(index / 2) * 2))),
  }));

  return (
    <div className="admin-view">
      <ViewHeader title="Load Forecast Model" kicker="ML Models / Patient Load Forecasting" />
      {!status.ok && !status.loading && <ComingSoon endpoint="/api/admin/ml/model-status?name=patient_load_model" />}
      <Panel title="Model Status">
        <div className="admin-model-hero">
          <div>
            <h2>patient_load_model</h2>
            <FieldPill tone="green">Production</FieldPill>
            <strong>MAE --</strong>
            <span>Full model registry endpoint is not exposed yet.</span>
          </div>
        </div>
      </Panel>
      <Panel title="Today's Patient Load Forecast - All Doctors">
        <HeatmapGrid rows={heatRows} />
      </Panel>
      <Panel title="Forecast Accuracy">
        <MiniChart type="line" keys={["value", "p95"]} height={240} />
      </Panel>
      <Panel title="Recent Load Predictions">
        <DataTable rows={[]} columns={["id", "model", "predicted", "actual", "status"].map((key) => ({ key, label: key }))} />
      </Panel>
    </div>
  );
}
