import { useState, useEffect } from "react";
import "./App.css";

const API = import.meta.env.VITE_API || "http://localhost:8000";

const won = (n) => (n == null ? "-" : n.toLocaleString("ko-KR") + "원");

// ── 임시저장 → 엑셀(CSV) 내보내기용 항목 정의 [표시명, 문서→값] ──
const EXPORT_FIELDS = [
  ["사업명", (d) => d.title || d.doc_id],
  ["발주기관", (d) => d.org || ""],
  ["예산(원)", (d) => (d.budget ?? "")],
  ["마감일", (d) => d.deadline || ""],
  ["게시일", (d) => d.posted || ""],
  ["문서유형", (d) => d.filetype || ""],
  ["요약", (d) => d.summary || ""],
  ["출처", (d) => d.source || "로컬DB"],
  ["문서ID", (d) => d.doc_id],
  ["링크", (d) => d.link || ""],
];
const DEFAULT_FIELDS = ["사업명", "발주기관", "예산(원)", "마감일"];

// 문서 카드에서 임시저장함에 담을 스냅샷(검색 결과가 바뀌어도 유지되게 값 복사)
const snapshot = (it) => ({
  doc_id: it.doc_id, title: it.title, org: it.org, budget: it.budget,
  deadline: it.deadline, posted: it.posted, filetype: it.filetype,
  summary: it.summary, link: it.link, source: it.source,
});

// CSV 셀 이스케이프(콤마·따옴표·개행 포함 시 큰따옴표로 감쌈)
const csvCell = (v) => {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};

const STATUS_ICON = { O: "✅", X: "❌", "?": "⚠️" };

// 적격성 판정도 적합도와 같은 체스 등급 배지로 통일
const VERDICT_GRADE = {
  "적격": { sym: "★", cls: "g-best" },       // 형식상 적격(통과) — '완벽'이 아님
  "확인필요": { sym: "?!", cls: "g-inacc" },
  "부적격": { sym: "??", cls: "g-blunder" },
};

function VerdictBadge({ verdict }) {
  const g = VERDICT_GRADE[verdict] || { sym: "?", cls: "g-mistake" };
  return <span className={"grade " + g.cls}><b>{g.sym}</b> {verdict}</span>;
}

// 적격성 결과: 1차 판정(적격/부적격) + O/X 근거 + ⚠️ 추가 확인(?) 항목 + 2차 입력란
function EligibilityResult({ data, docId, more, setMore, onRecheck }) {
  const definitive = data.items.filter((x) => x.status !== "?");
  const checks = data.items.filter((x) => x.status === "?");
  const showMore = checks.length > 0 || data.items.length === 0; // 추가확인 또는 추출실패 시 재판정 유도
  return (
    <div className="elig">
      <div className="elig-verdict">
        <VerdictBadge verdict={data.verdict} />
        <span className="ev-summary">{data.summary}</span>
      </div>
      {definitive.length > 0 && (
        <table className="kv-table elig-table">
          <tbody>
            {definitive.map((row, i) => (
              <tr key={i}>
                <th>{STATUS_ICON[row.status] || "•"}</th>
                <td><b>{row.requirement}</b><br /><span className="reason">{row.reason}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {showMore && (
        <div className="elig-checks">
          {checks.length > 0 && (
            <>
              <div className="checks-head">⚠️ 추가 확인이 필요한 항목 ({checks.length})</div>
              <ul className="checks-list">
                {checks.map((c, i) => <li key={i}><b>{c.requirement}</b> — {c.reason}</li>)}
              </ul>
            </>
          )}
          <textarea
            className="more-input"
            placeholder="위 항목 관련 정보를 적고 재판정하세요. 예) 유사 실적 3건·GS인증 1등급 보유, 컨소시엄 가능"
            value={more || ""}
            onChange={(e) => setMore(e.target.value)}
          />
          <button className="btn btn-ai" onClick={() => onRecheck(docId, more)}>추가 정보로 재판정</button>
        </div>
      )}
    </div>
  );
}

// 관련도(코사인)를 체스닷컴 스타일 등급으로 매핑
function fitGrade(score) {
  const s = Math.max(0, score);
  if (s >= 0.65) return { sym: "!!", label: "완벽 적합", cls: "g-brilliant" };
  if (s >= 0.57) return { sym: "!", label: "매우 적합", cls: "g-great" };
  if (s >= 0.50) return { sym: "★", label: "적합", cls: "g-best" };
  if (s >= 0.43) return { sym: "✓", label: "무난", cls: "g-good" };
  if (s >= 0.36) return { sym: "?!", label: "약한 관련", cls: "g-inacc" };
  if (s >= 0.28) return { sym: "?", label: "관련 낮음", cls: "g-mistake" };
  return { sym: "??", label: "부적합", cls: "g-blunder" };
}

function FitBadge({ score }) {
  const g = fitGrade(score);
  return (
    <span className={"grade " + g.cls} title={`관련도 ${Math.round(Math.max(0, score) * 100)}%`}>
      <b>{g.sym}</b> {g.label}
    </span>
  );
}

export default function App() {
  const [profile, setProfile] = useState("");
  const [q, setQ] = useState("");
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [org, setOrg] = useState("");
  const [deadline, setDeadline] = useState("");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("");
  const [summaries, setSummaries] = useState({});
  const [company, setCompany] = useState("");
  const [elig, setElig] = useState({});
  const [eligMore, setEligMore] = useState({}); // doc_id -> 2차 추가 정보
  // 임시저장함: { [doc_id]: { doc: 스냅샷, fields: [담을 항목명] } }. 새로고침해도 유지.
  const [saved, setSaved] = useState(() => {
    try { return JSON.parse(localStorage.getItem("rfp_saved") || "{}"); } catch { return {}; }
  });
  const [cartOpen, setCartOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem("rfp_saved", JSON.stringify(saved));
  }, [saved]);

  const savedCount = Object.keys(saved).length;

  function toggleSave(it) {
    setSaved((s) => {
      const next = { ...s };
      if (next[it.doc_id]) delete next[it.doc_id];
      else next[it.doc_id] = { doc: snapshot(it), fields: [...DEFAULT_FIELDS] };
      return next;
    });
  }

  function toggleField(docId, name) {
    setSaved((s) => {
      const entry = s[docId];
      if (!entry) return s;
      const has = entry.fields.includes(name);
      const fields = has ? entry.fields.filter((f) => f !== name) : [...entry.fields, name];
      return { ...s, [docId]: { ...entry, fields } };
    });
  }

  function removeSaved(docId) {
    setSaved((s) => { const n = { ...s }; delete n[docId]; return n; });
  }

  function clearCart() {
    if (savedCount && confirm("임시저장함을 전부 비울까요?")) setSaved({});
  }

  function exportCSV() {
    const rows = Object.values(saved);
    if (rows.length === 0) return alert("임시저장된 문서가 없습니다.");
    // 컬럼 = 어느 문서든 선택된 항목의 합집합(정의 순서 유지)
    const cols = EXPORT_FIELDS.filter(([name]) => rows.some((r) => r.fields.includes(name)));
    if (cols.length === 0) return alert("내보낼 항목이 하나도 선택되지 않았습니다.");
    const header = cols.map(([name]) => csvCell(name)).join(",");
    const body = rows
      .map((r) => cols.map(([name, get]) => (r.fields.includes(name) ? csvCell(get(r.doc)) : "")).join(","))
      .join("\r\n");
    const csv = "﻿" + header + "\r\n" + body; // BOM: 엑셀 한글 깨짐 방지
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `임시저장_RFP_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function recommend() {
    if (!profile.trim()) return alert("고객사 역량/관심 분야를 입력하세요.");
    setLoading(true);
    setMode("맞춤 추천");
    try {
      const body = {
        profile,
        top_k: 10,
        budget_min: budgetMin ? Number(budgetMin) : null,
        budget_max: budgetMax ? Number(budgetMax) : null,
        org: org || null,
        deadline_before: deadline || null,
      };
      const r = await fetch(`${API}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      setItems(j.items);
      setTotal(j.total);
    } catch (e) {
      alert("오류: " + e.message + "\n백엔드(uvicorn)가 켜져 있는지 확인하세요.");
    }
    setLoading(false);
  }

  async function listDocs() {
    setLoading(true);
    setMode("빠른 필터");
    try {
      const p = new URLSearchParams();
      if (q) p.set("q", q);
      if (budgetMin) p.set("budget_min", budgetMin);
      if (budgetMax) p.set("budget_max", budgetMax);
      if (org) p.set("org", org);
      if (deadline) p.set("deadline_before", deadline);
      p.set("limit", "50");
      const r = await fetch(`${API}/documents?` + p.toString());
      const j = await r.json();
      setItems(j.items);
      setTotal(j.total);
    } catch (e) {
      alert("오류: " + e.message + "\n백엔드(uvicorn)가 켜져 있는지 확인하세요.");
    }
    setLoading(false);
  }

  async function checkEligibility(docId, extra = "") {
    setElig((s) => ({ ...s, [docId]: { loading: true } }));
    try {
      const companyFull =
        [company, extra && "추가 정보: " + extra].filter(Boolean).join("\n") || null;
      const r = await fetch(`${API}/eligibility`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId, company: companyFull }),
      });
      const j = await r.json();
      setElig((s) => ({ ...s, [docId]: { loading: false, ...j } }));
    } catch (e) {
      setElig((s) => ({ ...s, [docId]: { loading: false, error: e.message } }));
    }
  }

  async function summarize(docId) {
    setSummaries((s) => ({ ...s, [docId]: { loading: true } }));
    try {
      const r = await fetch(`${API}/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId }),
      });
      const j = await r.json();
      setSummaries((s) => ({ ...s, [docId]: { loading: false, rows: j.rows, text: j.summary } }));
    } catch (e) {
      setSummaries((s) => ({ ...s, [docId]: { loading: false, text: "요약 실패: " + e.message } }));
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">📋</span>
          <div>
            <h1>입찰메이트</h1>
            <p>RFP 추천 · 요약 · 적격성 판정</p>
          </div>
        </div>
        <button className="btn btn-cart" onClick={() => setCartOpen(true)}>
          🗂 임시저장함{savedCount > 0 && <span className="cart-badge">{savedCount}</span>}
        </button>
      </header>

      {/* ── AI 추천 (LLM이 의미를 이해해 검색) ── */}
      <section className="hero">
        <div className="hero-label">
          <span className="chip chip-ai">✨ AI</span>
          <h2>AI 맞춤 추천</h2>
        </div>
        <p className="hero-hint">
          고객사 역량·관심을 <b>자연어로</b> 적으면, AI가 <b>의미를 이해</b>해 맞는 공고를 찾아 재정렬합니다.
        </p>
        <div className="hero-input">
          <textarea
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            placeholder="예) 대학 학사·포털 시스템 구축을 많이 해봤는데, 우리 회사에 맞는 공고를 찾아줘."
          />
          <button className="btn btn-ai-solid" onClick={recommend} disabled={loading}>
            {loading && mode === "맞춤 추천" ? (<><span className="spinner" /> AI가 찾는 중…</>) : "✨ AI로 추천받기"}
          </button>
        </div>
      </section>

      <div className="layout">
        <aside className="side">
          <div className="panel">
            <div className="panel-head">
              <h3>🔎 빠른 필터</h3>
              <span className="chip chip-plain">즉시 · AI 미사용</span>
            </div>
            <p className="hint">정확한 조건으로 바로 거릅니다.</p>
            <label>키워드<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="예: 학사, 버스" /></label>
            <div className="row2">
              <label>예산 최소<input type="number" value={budgetMin} onChange={(e) => setBudgetMin(e.target.value)} placeholder="원" /></label>
              <label>예산 최대<input type="number" value={budgetMax} onChange={(e) => setBudgetMax(e.target.value)} placeholder="원" /></label>
            </div>
            <label>발주기관<input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="예: 대학교" /></label>
            <label>마감 이전<input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
            <button className="btn btn-plain" onClick={listDocs}>필터로 목록 보기</button>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3>🏢 회사 프로필</h3>
              <span className="chip chip-ai">적격성용</span>
            </div>
            <p className="hint">적격성 판정에 사용. 자연어로 자유롭게.</p>
            <textarea
              className="company-input"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="예) 서울 소재 중소기업. 공공 SI·학사시스템 구축 3건, GS인증 1등급. 컨소시엄 가능."
            />
          </div>
        </aside>

        <main className="results">
          {mode && (
            <div className="results-bar">
              <span className={"mode-tag " + (mode === "맞춤 추천" ? "mode-ai" : "mode-plain")}>
                {mode === "맞춤 추천" ? "✨ AI 추천" : "🔎 필터"}
              </span>
              <span className="count">{loading ? "불러오는 중…" : `${total}건`}</span>
            </div>
          )}
          {!mode && !loading && (
            <div className="empty-hint">위에서 <b>AI 추천</b>을 받거나, 왼쪽 <b>빠른 필터</b>로 시작하세요.</div>
          )}

          <ul className="cards">
            {[...items].sort((a, b) => (b.score ?? -2) - (a.score ?? -2)).map((it) => (
              <li key={it.doc_id} className="card">
                <div className="card-top">
                  <h4 className="card-title">{it.title || it.doc_id}</h4>
                  <div className="badges">
                    {it.source && <span className="badge badge-src">🌐 {it.source}</span>}
                    {it.score != null && <FitBadge score={it.score} />}
                  </div>
                </div>

                <div className="meta">
                  <span>🏛 {it.org || "-"}</span>
                  <span>💰 {won(it.budget)}</span>
                  <span>📅 {it.deadline || "-"}</span>
                </div>

                {it.summary && <p className="snippet">{it.summary.slice(0, 130)}…</p>}
                {it.link && <a className="ext-link" href={it.link} target="_blank" rel="noreferrer">공고 상세 ↗</a>}

                <div className="card-actions">
                  <button className="btn btn-ai" onClick={() => summarize(it.doc_id)} disabled={summaries[it.doc_id]?.loading}>
                    {summaries[it.doc_id]?.loading ? (<><span className="spinner" /> 요약 중…</>) : "✨ AI 요약"}
                  </button>
                  <button className="btn btn-ai" onClick={() => checkEligibility(it.doc_id)} disabled={elig[it.doc_id]?.loading}>
                    {elig[it.doc_id]?.loading ? (<><span className="spinner" /> 판정 중…</>) : "⚖️ 적격성 판정"}
                  </button>
                  <button
                    className={"btn " + (saved[it.doc_id] ? "btn-saved" : "btn-save")}
                    onClick={() => toggleSave(it)}
                  >
                    {saved[it.doc_id] ? "⭐ 저장됨" : "☆ 임시저장"}
                  </button>
                </div>

                {saved[it.doc_id] && (
                  <div className="save-fields">
                    <span className="sf-label">📊 엑셀에 담을 항목</span>
                    <div className="sf-checks">
                      {EXPORT_FIELDS.map(([name]) => (
                        <label key={name} className="sf-check">
                          <input
                            type="checkbox"
                            checked={saved[it.doc_id].fields.includes(name)}
                            onChange={() => toggleField(it.doc_id, name)}
                          />
                          {name}
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {summaries[it.doc_id]?.rows?.length > 0 ? (
                  <table className="kv-table">
                    <tbody>
                      {summaries[it.doc_id].rows.map((row) => (
                        <tr key={row.label}>
                          <th>{row.label}</th>
                          <td>{row.value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  summaries[it.doc_id]?.text && <pre className="raw-summary">{summaries[it.doc_id].text}</pre>
                )}

                {elig[it.doc_id]?.items && (
                  <EligibilityResult
                    data={elig[it.doc_id]}
                    docId={it.doc_id}
                    more={eligMore[it.doc_id]}
                    setMore={(v) => setEligMore((s) => ({ ...s, [it.doc_id]: v }))}
                    onRecheck={checkEligibility}
                  />
                )}
                {elig[it.doc_id]?.error && <p className="err">판정 실패: {elig[it.doc_id].error}</p>}
              </li>
            ))}
          </ul>

          {!loading && mode && items.length === 0 && (
            <div className="empty-result">
              {mode === "맞춤 추천"
                ? "조건에 맞는 적합한 공고를 찾지 못했어요. 질문을 바꾸거나 나라장터 연동을 켜보세요."
                : "결과가 없습니다."}
            </div>
          )}
        </main>
      </div>

      {cartOpen && (
        <div className="modal-backdrop" onClick={() => setCartOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>🗂 임시저장함 <span className="mh-count">{savedCount}건</span></h3>
              <button className="modal-x" onClick={() => setCartOpen(false)}>✕</button>
            </div>
            {savedCount === 0 ? (
              <p className="cart-empty">아직 담긴 문서가 없어요.<br />문서 카드의 <b>☆ 임시저장</b>을 눌러 담고, 담을 항목을 체크하세요.</p>
            ) : (
              <>
                <ul className="cart-list">
                  {Object.values(saved).map((r) => (
                    <li key={r.doc.doc_id} className="cart-item">
                      <div className="ci-main">
                        <div className="ci-title">{r.doc.title || r.doc.doc_id}</div>
                        <div className="ci-fields">
                          {r.fields.length ? r.fields.join(" · ") : <span className="ci-none">담긴 항목 없음 — 카드에서 체크하세요</span>}
                        </div>
                      </div>
                      <button className="ci-del" onClick={() => removeSaved(r.doc.doc_id)} title="삭제">✕</button>
                    </li>
                  ))}
                </ul>
                <div className="cart-actions">
                  <button className="btn btn-plainline" onClick={clearCart}>전체 비우기</button>
                  <button className="btn btn-ai-solid" onClick={exportCSV}>⬇ 엑셀(CSV)로 저장</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
