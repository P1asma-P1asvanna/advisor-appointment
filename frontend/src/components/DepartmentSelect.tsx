import { api } from "../api/endpoints";
import { useLoad } from "../lib/hooks";

/** Department pick-list (grouped by faculty, list kept on the server). A value the person already has
 *  that is no longer in the list stays selectable, so an unrelated edit never forces a change. */
export default function DepartmentSelect({ value, onChange, required }: { value: string; onChange(v: string): void; required?: boolean }) {
  const list = useLoad(() => api.departments(), []);
  const groups = list.data?.groups ?? [];
  const known = groups.some((g) => g.departments.includes(value));
  return (
    <select required={required} value={value} onChange={(e) => onChange(e.target.value)} disabled={list.loading}>
      <option value="">{list.loading ? "กำลังโหลด…" : list.error ? "โหลดรายการไม่สำเร็จ" : "— เลือกภาควิชา —"}</option>
      {value && !known && !list.loading && <option value={value}>{value} (ค่าเดิม ไม่อยู่ในรายการ)</option>}
      {groups.map((g) => (
        <optgroup key={g.faculty} label={g.faculty}>
          {g.departments.map((d) => <option key={d} value={d}>{d}</option>)}
        </optgroup>
      ))}
    </select>
  );
}
