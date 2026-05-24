import { useMemo, useState } from "react";

export default function DataTable({ columns, rows = [], pageSize = 12, empty = "No rows available" }) {
  const [sort, setSort] = useState(null);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((item) => item.key === sort.key);
    return [...rows].sort((a, b) => {
      const av = column?.sortValue ? column.sortValue(a) : a[sort.key];
      const bv = column?.sortValue ? column.sortValue(b) : b[sort.key];
      return String(av ?? "").localeCompare(String(bv ?? "")) * (sort.dir === "asc" ? 1 : -1);
    });
  }, [rows, columns, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const visible = sorted.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>
                <button
                  type="button"
                  onClick={() =>
                    setSort((current) =>
                      current?.key === column.key
                        ? { key: column.key, dir: current.dir === "asc" ? "desc" : "asc" }
                        : { key: column.key, dir: "asc" },
                    )
                  }
                >
                  {column.label}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="admin-table__empty">
                {empty}
              </td>
            </tr>
          ) : (
            visible.map((row, index) => (
              <tr key={row.id || row.run_id || index}>
                {columns.map((column) => (
                  <td key={column.key}>{column.render ? column.render(row) : row[column.key]}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      <div className="admin-pagination">
        <button type="button" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>
          Prev
        </button>
        <span>
          Page {page + 1} of {pages}
        </span>
        <button type="button" disabled={page + 1 >= pages} onClick={() => setPage((value) => value + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}
