import { useState } from "react";
import { money, moneySigned, num, verdictMeta } from "../format";


// Pure presentation: given an AnalysisResult, render the dashboard.
// No fetching here — data flows in via props (single source of truth in App).
export default function ResultDashboard({ result }) {
  const { listing } = result;
  const v = verdictMeta(result.verdict);

  const marketMid = Math.round((result.market_low + result.market_high) / 2);
  const diffPositive = result.price_diff < 0; // below market = good for buyer

  return (
    <section className="dash">
      <div className="section-title">02 / Analiz Sonucu</div>

      {/* Top: verdict (wide) + visualizer (interactive) + score (narrow) */}
      <div className="dash__top">
        <div className="panel verdict">
          <div className="verdict__head">
            <span className={`verdict__badge ${v.cls}`}>{v.label}</span>
            <div>
              <div className="verdict__car">
                {[listing.brand, listing.model].filter(Boolean).join(" ") || "Araç"}
              </div>
              <div className="label" style={{ marginTop: 4 }}>
                {listing.year || "—"} MODEL
              </div>
            </div>
          </div>
          <div className="verdict__meta">
            <span>KM <b>{num(listing.km)}</b></span>
            <span>YAKIT <b>{listing.fuel_type || "—"}</b></span>
            <span>VİTES <b>{listing.transmission || "—"}</b></span>
          </div>
        </div>


        <div className="panel score">
          <div className="label">FIRSAT SKORU</div>
          <div className="score__num">
            {result.opportunity_score}<small>/100</small>
          </div>
          <div className="score__bar">
            <div 
              className="score__fill" 
              style={{ width: `${result.opportunity_score}%` }} 
              role="progressbar" 
              aria-valuenow={result.opportunity_score} 
              aria-valuemin="0" 
              aria-valuemax="100" 
            />
          </div>
        </div>
      </div>

      {/* Price strip: the numbers are the hero */}
      <div className="prices">
        <div className="stat">
          <div className="stat__label">İlan Fiyatı</div>
          <div className="stat__value">{money(listing.listed_price)}</div>
        </div>
        <div className="stat">
          <div className="stat__label">Piyasa Aralığı (Gemini)</div>
          <div className="stat__value">{money(result.market_low)}</div>
          <div className="stat__sub">→ {money(result.market_high)}</div>
        </div>
        <div className="stat">
          <div className="stat__label">Piyasa Farkı</div>
          <div className={`stat__value ${diffPositive ? "stat__value--pos" : "stat__value--neg"}`}>
            {diffPositive ? `${money(Math.abs(result.price_diff))} (Piyasa Altı)` : moneySigned(result.price_diff)}
          </div>
          <div className="stat__sub">orta nokta {money(marketMid)}</div>
        </div>
        <div className="stat">
          <div className="stat__label">Model Tahmini (ML)</div>
          <div className="stat__value">{result.predicted_price ? money(result.predicted_price) : "—"}</div>
          <div className="stat__sub">{result.predicted_price ? "scikit-learn" : "model eğitilmedi"}</div>
        </div>
      </div>

      {/* Pros / cons */}
      <div className="proscons">
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>ARTILAR</div>
          <ul className="list list--pros">
            {result.pros.length ? result.pros.map((p, i) => <li key={i}>{p}</li>) : <li>—</li>}
          </ul>
        </div>
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>EKSİLER / RİSKLER</div>
          <ul className="list list--cons">
            {result.cons.length ? result.cons.map((c, i) => <li key={i}>{c}</li>) : <li>—</li>}
          </ul>
        </div>
      </div>

      {/* Chronic Issues and User Consensus */}
      {(result.chronic_issues?.length > 0 || result.user_consensus) && (
        <div className="two-col" style={{ marginTop: 24 }}>
          {result.chronic_issues?.length > 0 && (
            <div className="panel" style={{ borderLeft: '4px solid var(--danger)', backgroundColor: 'rgba(239, 68, 68, 0.05)' }}>
              <div className="label" style={{ marginBottom: 12, color: 'var(--danger)' }}>⚠️ KRONİK SORUNLAR & DİKKAT EDİLMESİ GEREKENLER</div>
              <ul className="list list--cons">
                {result.chronic_issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            </div>
          )}
          {result.user_consensus && (
            <div className="panel" style={{ borderLeft: '4px solid var(--accent)', backgroundColor: 'rgba(56, 189, 248, 0.05)' }}>
              <div className="label" style={{ marginBottom: 12, color: 'var(--accent)' }}>🗣️ KULLANICI DENEYİMİ</div>
              <p className="prose">{result.user_consensus}</p>
            </div>
          )}
        </div>
      )}

      {/* Negotiation + expert commentary */}
      <div className="two-col">
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>PAZARLIK REHBERİ</div>
          <p className="prose">{result.negotiation_guide}</p>
        </div>
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>UZMAN YORUMU</div>
          <p className="prose">{result.expert_comment}</p>
        </div>
      </div>
    </section>
  );
}
