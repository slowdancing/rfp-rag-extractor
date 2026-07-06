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
  const [summaries, setSummaries] = useState({}); // doc_id -> {loading, text}
  const [company, setCompany] = useState(""); // 회사 소개(자연어)
  const [elig, setElig] = useState({}); // doc_id -> {loading, verdict, summary, items}

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
    setMode("필터 목록");
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
      <header>
        <h1>📋 입찰메이트 — RFP 추천·검색</h1>
        <p>고객사에 맞는 입찰 공고(RFP)를 찾고, 필요하면 AI 요약으로 핵심만 확인하세요.</p>
      </header>

      <div className="layout">
        <aside className="filters">
          <h3>🔎 필터</h3>
          <label>키워드<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="예: 학사, 버스" /></label>
          <label>예산 최소(원)<input type="number" value={budgetMin} onChange={(e) => setBudgetMin(e.target.value)} /></label>
          <label>예산 최대(원)<input type="number" value={budgetMax} onChange={(e) => setBudgetMax(e.target.value)} /></label>
          <label>발주기관<input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="예: 대학교" /></label>
          <label>마감 이전<input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
          <button onClick={listDocs}>필터로 목록 보기</button>

          <h3 style={{ marginTop: 20 }}>🏢 회사 프로필</h3>
          <p className="muted" style={{ margin: "0 0 8px" }}>적격성 판정에 사용. 자연어로 자유롭게 적으세요.</p>
          <textarea
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="예) 서울 소재 중소기업. 공공 SI·대학 학사시스템 구축 3건, GS인증 1등급 보유. 컨소시엄 가능."
            style={{ minHeight: 90 }}
          />
        </aside>

        <main>
          <div className="recommend-box">
            <textarea
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              placeholder="고객사 역량·관심 분야 입력. 예) 대학 학사정보시스템 구축 전문, 클라우드 마이그레이션 경험 보유"
            />
            <button className="primary" onClick={recommend}>🎯 맞춤 RFP 추천</button>
          </div>

          {loading && <p className="muted">불러오는 중…</p>}
          {!loading && mode && <p className="muted">{mode} · {total}건</p>}

          <ul className="cards">
            {items.map((it) => (
              <li key={it.doc_id} className="card">
                <div className="card-head">
                  <h4>{it.title || it.doc_id}</h4>
                  {it.score != null && (
                    <span className="score">관련도 {Math.round(Math.max(0, it.score) * 100)}%</span>
                  )}
                  {it.source && <span className="score">{it.source}</span>}
                </div>
                <div className="meta">
                  <span>🏛 {it.org || "-"}</span>
                  <span>💰 {won(it.budget)}</span>
                  <span>📅 마감 {it.deadline || "-"}</span>
                </div>
                {it.summary && <p className="summary-line">{it.summary.slice(0, 130)}…</p>}
                <button
                  className="ai-btn"
                  onClick={() => summarize(it.doc_id)}
                  disabled={summaries[it.doc_id]?.loading}
                >
                  {summaries[it.doc_id]?.loading ? "AI 요약 생성 중…" : "📄 AI 요약"}
                </button>
                {summaries[it.doc_id]?.rows?.length > 0 ? (
                  <table className="ai-summary-table">
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
                  summaries[it.doc_id]?.text && (
                    <pre className="ai-summary">{summaries[it.doc_id].text}</pre>
                  )
                )}
                <button
                  className="ai-btn"
                  onClick={() => checkEligibility(it.doc_id)}
                  disabled={elig[it.doc_id]?.loading}
                >
                  {elig[it.doc_id]?.loading ? "적격성 판정 중…" : "⚖️ 적격성 판정"}
                </button>
                {elig[it.doc_id]?.items && (
                  <div className="elig">
                    <div className={"elig-verdict " + (VERDICT_CLASS[elig[it.doc_id].verdict] || "")}>
                      {elig[it.doc_id].verdict} — {elig[it.doc_id].summary}
                    </div>
                    {elig[it.doc_id].items.length > 0 && (
                      <table className="ai-summary-table">
                        <tbody>
                          {elig[it.doc_id].items.map((row, i) => (
                            <tr key={i}>
                              <th>{STATUS_ICON[row.status] || "⚠️"}</th>
                              <td><b>{row.requirement}</b><br />{row.reason}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
                {elig[it.doc_id]?.error && <p className="muted">판정 실패: {elig[it.doc_id].error}</p>}
              </li>
            ))}
          </ul>
          {!loading && mode && items.length === 0 && (
            <p className="muted">
              {mode === "맞춤 추천"
                ? "조건에 맞는 적합한 공고를 찾지 못했어요. (질문을 바꾸거나 나라장터 연동을 켜보세요)"
                : "결과가 없습니다."}
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
