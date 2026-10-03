import { useState } from "react";
import { dateTimeStr, titleCase, useFetch } from "../../lib/hooks";
import { Card, Empty, ErrorBox, PageHead, Spinner } from "../../components/ui";

interface Row { id: number; at: string; user: string | null; action: string; entity: string | null; entity_id: number | null; detail: string | null; ip: string | null }

export default function AuditLog() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useFetch<{ total: number; items: Row[] }>(`/audit?page=${page}&page_size=50`);
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <>
      <PageHead title="Audit log" subtitle="Every sign-in, mark change, result publication and configuration change." />
      <Card pad={false}>
        {loading && !data ? <Spinner /> : error ? <div style={{ padding: 16 }}><ErrorBox error={error} onRetry={reload} /></div> : !data?.items.length ? <Empty title="No activity yet" /> : (
          <div className="table-wrap"><table className="table compact">
            <thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Detail</th><th>IP</th></tr></thead>
            <tbody>{data.items.map((r) => (
              <tr key={r.id}>
                <td className="small nowrap">{dateTimeStr(r.at)}</td><td className="small">{r.user ?? "—"}</td>
                <td><span className={`badge ${r.action === "login_failed" ? "badge-bad" : ""}`}>{titleCase(r.action)}</span></td>
                <td className="small">{r.entity ? `${r.entity} #${r.entity_id ?? ""}` : "—"}</td>
                <td className="small text-2" style={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={r.detail ?? ""}>{r.detail ?? ""}</td>
                <td className="small muted">{r.ip}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        {pages > 1 && <div className="row" style={{ padding: 12, justifyContent: "flex-end" }}>
          <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Newer</button>
          <span className="small">Page {page} of {pages}</span>
          <button className="btn btn-sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Older →</button>
        </div>}
      </Card>
    </>
  );
}
