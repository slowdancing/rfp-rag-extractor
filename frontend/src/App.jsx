import { useState } from "react";
import "./App.css";

const API = import.meta.env.VITE_API || "http://localhost:8000";

const won = (n) => (n == null ? "-" : n.toLocaleString("ko-KR") + "원");

const VERDICT_CLASS = { "적격": "v-ok", "부적격": "v-no", "확인필요": "v-maybe" };
const STATUS_ICON = { O: "✅", X: "❌", "?": "⚠️" };

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

  async function checkEligibility(docId) {
    setElig((s) => ({ ...s, [docId]: { loading: true } }));
    try {
      const r = await fetch(`${API}/eligibility`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId, company: company || null }),
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
            {items.map((it) => (
              <li key={it.doc_id} className="card">
                <div className="card-top">
                  <h4 className="card-title">{it.title || it.doc_id}</h4>
                  <div className="badges">
                    {it.source && <span className="badge badge-src">🌐 {it.source}</span>}
                    {it.score != null && (
                      <span className="badge badge-score">관련도 {Math.round(Math.max(0, it.score) * 100)}%</span>
                    )}
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
                </div>

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
                  <div className="elig">
                    <div className={"elig-verdict " + (VERDICT_CLASS[elig[it.doc_id].verdict] || "")}>
                      <b>{elig[it.doc_id].verdict}</b> — {elig[it.doc_id].summary}
                    </div>
                    {elig[it.doc_id].items.length > 0 && (
                      <table className="kv-table elig-table">
                        <tbody>
                          {elig[it.doc_id].items.map((row, i) => (
                            <tr key={i}>
                              <th>{STATUS_ICON[row.status] || "⚠️"}</th>
                              <td><b>{row.requirement}</b><br /><span className="reason">{row.reason}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
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
    </div>
  );
}
