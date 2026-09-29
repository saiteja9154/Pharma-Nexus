import React, { useState } from 'react';
import {
  Bot,
  Play,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Shield,
  Cpu,
  Package,
  Calendar,
  Layers,
  Terminal,
  Clock,
  ArrowRight,
  Truck,
  Award,
  DollarSign,
  TrendingDown,
  MessageSquare,
  ShoppingCart,
  ShieldCheck,
  Check,
  RefreshCw,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function AgentControl() {
  const [running, setRunning] = useState(false);
  const [executingMedId, setExecutingMedId] = useState(null);
  const [agentResult, setAgentResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [execSuccessMsg, setExecSuccessMsg] = useState(null);

  const handleRunAgent = async () => {
    setRunning(true);
    setErrorMsg(null);
    setExecSuccessMsg(null);
    try {
      const res = await fetch(`${API_BASE}/procurement/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to execute StoreAgent`);
      }
      const data = await res.json();
      setAgentResult(data);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to connect to backend StoreAgent');
    } finally {
      setRunning(false);
    }
  };

  const handleExecuteProcurement = async (medicineId) => {
    setExecutingMedId(medicineId);
    setErrorMsg(null);
    setExecSuccessMsg(null);
    try {
      const res = await fetch(`${API_BASE}/procurement/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medicine_id: medicineId }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to execute purchase order`);
      }
      const execData = await res.json();

      if (!execData.success) {
        throw new Error(execData.message || execData.error || 'Execution blocked by guard');
      }

      // Update state locally
      setAgentResult((prev) => {
        if (!prev) return prev;
        const updatedMeds = prev.medicines.map((m) => {
          if (m.med_id === medicineId) {
            return {
              ...m,
              current_stock: execData.inventory?.after ?? m.current_stock,
              po: execData.po,
              execution_result: execData.execution_result,
              decision_reason: `Purchase Order ${execData.po?.po_number || `PO-#${execData.po?.po_id}`} created and inventory restocked to ${execData.inventory?.after} units.`,
            };
          }
          return m;
        });

        const newLog = {
          step: 'CREATE_PO',
          message: `Phase 6: Created ${execData.po?.po_number || `PO-#${execData.po?.po_id}`} for ${execData.po?.medicine_name} (${execData.po?.quantity} units @ $${Number(execData.po?.unit_price).toFixed(2)}/u = $${Number(execData.po?.total_cost).toFixed(2)}). Stock updated: ${execData.inventory?.before} -> ${execData.inventory?.after}.`,
        };

        return {
          ...prev,
          medicines: updatedMeds,
          logs: [...prev.logs, newLog],
        };
      });

      setExecSuccessMsg(`Successfully executed PO #${execData.po?.po_id} for ${execData.po?.medicine_name}. Stock updated: ${execData.inventory?.before} → ${execData.inventory?.after}.`);
    } catch (err) {
      setErrorMsg(err.message || 'Execution failed');
    } finally {
      setExecutingMedId(null);
    }
  };

  const getStepBadgeClass = (step) => {
    switch (step) {
      case 'OBSERVE':
        return 'badge-blue';
      case 'CALCULATE':
        return 'badge-purple';
      case 'VERIFY':
        return 'badge-amber';
      case 'GET_QUOTES':
        return 'badge-blue';
      case 'SCORE':
        return 'badge-purple';
      case 'SELECT_VENDOR':
        return 'badge-green';
      case 'NEGOTIATE':
      case 'OFFER':
      case 'COUNTER':
        return 'badge-purple';
      case 'VENDOR_RESPONSE':
      case 'ADAPT':
        return 'badge-amber';
      case 'ACCEPT':
      case 'VALIDATE':
        return 'badge-green';
      case 'CREATE_PO':
      case 'COMPLETE':
        return 'badge-green';
      default:
        return 'badge-blue';
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Bot size={28} color="#818cf8" />
            Agent Control Center
          </h1>
          <p className="page-subtitle">
            Autonomous Restocking, Bargaining & ERP Write-Back Orchestrator (Phase 6)
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button
            id="btn-run-agent"
            onClick={handleRunAgent}
            className="btn btn-primary"
            disabled={running}
            style={{ padding: '0.75rem 1.5rem', fontSize: '0.95rem' }}
          >
            {running ? (
              <>
                <RefreshCw size={18} className="spinner" />
                <span>StoreAgent Orchestrating...</span>
              </>
            ) : (
              <>
                <Play size={18} fill="currentColor" />
                <span>Run Store Procurement Agent</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Run Execution Metadata Banner */}
      {agentResult && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--bg-subtle)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '0.75rem 1.25rem',
            marginBottom: '1.25rem',
            fontSize: '0.85rem',
            flexWrap: 'wrap',
            gap: '0.75rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span className="badge badge-green font-mono" style={{ fontWeight: 800 }}>
              <CheckCircle2 size={13} />
              FRESH SQLITE RUN
            </span>
            <span style={{ color: 'var(--text-muted)' }}>
              Run ID: <strong className="font-mono" style={{ color: '#38bdf8' }}>{agentResult.run_id ? agentResult.run_id.slice(0, 8) : 'ACTIVE'}</strong>
            </span>
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>
            Started: {agentResult.timestamp ? new Date(agentResult.timestamp).toLocaleTimeString() : 'Just now'} &bull; Status: <strong style={{ color: '#34d399', textTransform: 'uppercase' }}>{agentResult.status}</strong>
          </div>
        </div>
      )}

      {errorMsg && (
        <div className="error-box">
          <AlertCircle size={20} />
          <div>
            <strong>Execution Error:</strong> {errorMsg}
          </div>
        </div>
      )}

      {execSuccessMsg && (
        <div className="card" style={{ background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.4)', padding: '1rem 1.25rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <CheckCircle2 size={20} color="#34d399" />
          <span style={{ color: '#34d399', fontWeight: 600 }}>{execSuccessMsg}</span>
        </div>
      )}

      {/* KPI Stats Banner */}
      {agentResult && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
              <CheckCircle2 size={24} />
            </div>
            <div>
              <div className="stat-label">Agent Status</div>
              <div className="stat-value" style={{ textTransform: 'capitalize', color: '#34d399' }}>
                {agentResult.status}
              </div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(2, 132, 199, 0.15)', color: '#38bdf8' }}>
              <Layers size={24} />
            </div>
            <div>
              <div className="stat-label">Evaluated</div>
              <div className="stat-value">{agentResult.medicines_evaluated || agentResult.medicines?.length || 0} Meds</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
              <Award size={24} />
            </div>
            <div>
              <div className="stat-label">Vendors Selected</div>
              <div className="stat-value" style={{ color: '#fbbf24' }}>
                {agentResult.selected_vendor_count !== undefined
                  ? agentResult.selected_vendor_count
                  : agentResult.medicines?.filter((m) => m.selected_vendor).length}
              </div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa' }}>
              <TrendingDown size={24} />
            </div>
            <div>
              <div className="stat-label">Negotiated Savings</div>
              <div className="stat-value" style={{ color: '#a78bfa' }}>
                ${agentResult.medicines
                  ?.reduce((sum, m) => sum + (m.best_offer?.savings || 0), 0)
                  .toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Autonomous Vendor Selection Cards */}
      {agentResult && agentResult.medicines && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginBottom: '1.5rem' }}>
          {agentResult.medicines.map((med) => {
            const best = med.best_offer || med.negotiation?.best_offer;
            const isAccepted = med.decision === 'ACCEPT' && med.validation_result?.valid;
            const hasPO = med.po && med.po.po_id;
            const isHealthy = med.decision === 'NO_PROCUREMENT';

            return (
              <div key={med.med_id} className="card" id={`med-card-${med.med_id}`}>
                <div className="card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <Package size={20} color="#38bdf8" />
                    <div>
                      <h2 className="card-title" style={{ display: 'inline', marginRight: '0.5rem' }}>
                        {med.name}
                      </h2>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>ID #{med.med_id}</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span className="badge badge-blue">
                      Stock: {med.current_stock} / Reorder: {med.reorder_point}
                    </span>
                    {med.required_qty > 0 ? (
                      <span className="badge badge-purple" style={{ fontWeight: 700 }}>
                        Required: {med.required_qty} units
                      </span>
                    ) : (
                      <span className="badge badge-green" style={{ fontWeight: 700 }}>
                        Adequate Stock (0 Required)
                      </span>
                    )}
                  </div>
                </div>

                <div className="card-body">
                  {/* Winner Spotlight Banner with Negotiated Terms */}
                  {med.selected_vendor ? (
                    <div
                      style={{
                        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(6, 182, 212, 0.08))',
                        border: '1px solid rgba(16, 185, 129, 0.35)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem 1.25rem',
                        marginBottom: '1.25rem',
                        display: 'flex',
                        flexWrap: 'wrap',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '1rem',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                          <Award size={18} color="#34d399" />
                          <span style={{ fontWeight: 800, color: '#34d399', fontSize: '1rem' }}>
                            Winner: {med.selected_vendor.vendor_name}
                          </span>
                          <span className="badge badge-green" style={{ fontWeight: 800 }}>
                            Score: {med.selected_vendor.score.toFixed(1)} / 100
                          </span>
                          {med.decision && (
                            <span className={`badge ${med.decision === 'ACCEPT' ? 'badge-green' : med.decision === 'SWITCH_VENDOR' ? 'badge-amber' : 'badge-rose'}`} style={{ fontWeight: 800 }}>
                              DECISION: {med.decision}
                            </span>
                          )}
                          {hasPO ? (
                            <span className="badge badge-green" style={{ fontWeight: 800, background: 'rgba(16, 185, 129, 0.25)' }}>
                              <CheckCircle2 size={13} />
                              PO CREATED ({med.po.po_number || `PO-#${med.po.po_id}`})
                            </span>
                          ) : isAccepted ? (
                            <span className="badge badge-amber font-mono" style={{ fontWeight: 700 }}>
                              Ready for ERP PO Creation
                            </span>
                          ) : null}
                          {best && (
                            <span className="badge badge-purple font-mono" style={{ fontWeight: 700 }}>
                              <TrendingDown size={12} />
                              Saved ${best.savings.toFixed(2)} ({best.discount_pct}%)
                            </span>
                          )}
                        </div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          {med.decision_reason}
                        </p>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', gap: '1.25rem', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                          <div>
                            <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>INITIAL BASE</div>
                            <div style={{ color: 'var(--text-muted)', fontWeight: 700, textDecoration: best ? 'line-through' : 'none' }}>
                              ${med.selected_vendor.base_price.toFixed(2)}
                            </div>
                          </div>
                          <div>
                            <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>AGREED UNIT PRICE</div>
                            <div style={{ color: '#38bdf8', fontWeight: 800 }}>
                              ${best ? best.unit_price.toFixed(2) : med.selected_vendor.base_price.toFixed(2)}
                            </div>
                          </div>
                          <div>
                            <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>TOTAL COMMITMENT</div>
                            <div style={{ color: '#34d399', fontWeight: 800 }}>
                              ${best ? best.total_cost.toFixed(2) : med.selected_vendor.total_cost.toFixed(2)}
                            </div>
                          </div>
                          <div>
                            <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>DELIVERY SLA</div>
                            <div style={{ color: '#fbbf24', fontWeight: 700 }}>{med.selected_vendor.delivery_days}d</div>
                          </div>
                        </div>

                        {/* Phase 6 Execution CTA Button */}
                        {isAccepted && !hasPO && (
                          <button
                            id={`btn-execute-po-${med.med_id}`}
                            onClick={() => handleExecuteProcurement(med.med_id)}
                            className="btn btn-primary"
                            disabled={executingMedId === med.med_id}
                            style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', background: '#059669', borderColor: '#10b981' }}
                          >
                            <ShoppingCart size={15} />
                            <span>{executingMedId === med.med_id ? 'Writing to ERP...' : 'Execute Procurement & Write to ERP'}</span>
                          </button>
                        )}
                        {hasPO && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.4)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.75rem' }}>
                            <ShieldCheck size={16} color="#34d399" />
                            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#34d399' }}>
                              Committed to ERP: {med.po.po_number || `PO-#${med.po.po_id}`}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : isHealthy ? (
                    <div
                      style={{
                        background: 'rgba(16, 185, 129, 0.08)',
                        border: '1px solid rgba(16, 185, 129, 0.25)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem 1.25rem',
                        marginBottom: '1.25rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                      }}
                    >
                      <CheckCircle2 size={22} color="#34d399" />
                      <div>
                        <div style={{ fontWeight: 700, color: '#34d399', fontSize: '0.95rem' }}>
                          Adequate Stock &mdash; No Procurement Required
                        </div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                          {med.decision_reason} (Stock {med.current_stock} &gt;= Reorder {med.reorder_point}). Expiry: {med.expiry?.expiry_days_left} days left.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="error-box" style={{ marginBottom: '1.25rem' }}>
                      <AlertCircle size={18} />
                      <span>{med.decision_reason || 'No feasible vendor available.'}</span>
                    </div>
                  )}

                  {/* Phase 5 Deal Validation Breakdown */}
                  {med.validation_result && med.validation_result.checks && (
                    <div
                      style={{
                        background: 'var(--bg-subtle)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem 1.25rem',
                        marginBottom: '1.25rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                        <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                          Phase 5 Multi-Constraint Deal Validation
                        </div>
                        <span className={`badge ${med.validation_result.valid ? 'badge-green' : 'badge-rose'}`} style={{ fontWeight: 800 }}>
                          {med.validation_result.valid ? '✓ ALL 7 CONSTRAINTS PASSED' : '✗ VALIDATION FAILED'}
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem' }}>
                        {Object.entries(med.validation_result.checks).map(([checkKey, isPassed]) => (
                          <div
                            key={checkKey}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.4rem',
                              fontSize: '0.8rem',
                              padding: '0.4rem 0.6rem',
                              borderRadius: 'var(--radius-sm)',
                              background: isPassed ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.08)',
                              border: `1px solid ${isPassed ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)'}`,
                            }}
                          >
                            <span style={{ color: isPassed ? '#34d399' : '#fb7185', fontWeight: 800 }}>
                              {isPassed ? '✓' : '✗'}
                            </span>
                            <span style={{ color: isPassed ? 'var(--text-main)' : '#fb7185', textTransform: 'capitalize' }}>
                              {checkKey.replace('_', ' ')}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Candidate Quotes Comparison Table */}
                  {med.vendor_quotes && med.vendor_quotes.length > 0 && (
                    <div>
                      <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                        Candidate Vendor Offers Evaluation & Scoring
                      </div>
                      <div className="table-container">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Supplier</th>
                              <th>Unit Price</th>
                              <th>MOQ vs Required</th>
                              <th>Offered Qty</th>
                              <th>Total Cost</th>
                              <th>Delivery</th>
                              <th>Feasibility</th>
                              <th>Multi-Factor Score</th>
                              <th>Trade-off Rationale</th>
                            </tr>
                          </thead>
                          <tbody>
                            {med.vendor_quotes.map((quote) => {
                              const isSelected = med.selected_vendor && med.selected_vendor.vendor_id === quote.vendor_id;
                              return (
                                <tr
                                  key={quote.vendor_id}
                                  style={{
                                    background: isSelected ? 'rgba(16, 185, 129, 0.08)' : 'transparent',
                                  }}
                                >
                                  <td>
                                    <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                      {isSelected && <Award size={14} color="#34d399" />}
                                      <span>{quote.vendor_name}</span>
                                    </div>
                                  </td>
                                  <td>
                                    <span className="font-mono" style={{ color: '#38bdf8', fontWeight: 600 }}>
                                      ${quote.base_price.toFixed(2)}
                                    </span>
                                  </td>
                                  <td>
                                    <span className="font-mono" style={{ fontSize: '0.85rem' }}>
                                      MOQ: {quote.moq} (Req: {quote.required_qty})
                                    </span>
                                  </td>
                                  <td>
                                    <span className="font-mono" style={{ fontWeight: 700 }}>
                                      {quote.offered_qty} units
                                    </span>
                                  </td>
                                  <td>
                                    <span className="font-mono" style={{ color: '#34d399', fontWeight: 700 }}>
                                      ${quote.total_cost.toFixed(2)}
                                    </span>
                                  </td>
                                  <td>
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                      <Clock size={13} color="var(--text-muted)" />
                                      {quote.delivery_days}d
                                    </span>
                                  </td>
                                  <td>
                                    {quote.feasible ? (
                                      <span className="badge badge-green">✓ Feasible</span>
                                    ) : (
                                      <span className="badge badge-rose">✗ Infeasible</span>
                                    )}
                                  </td>
                                  <td>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                      <span
                                        className="font-mono"
                                        style={{
                                          fontWeight: 800,
                                          fontSize: '1rem',
                                          color: isSelected ? '#34d399' : quote.feasible ? '#38bdf8' : '#fb7185',
                                        }}
                                      >
                                        {quote.score.toFixed(1)}
                                      </span>
                                    </div>
                                  </td>
                                  <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '240px' }}>
                                    {quote.reasons ? quote.reasons.join(' • ') : '-'}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Agent Structured Execution Trace Logs */}
      {agentResult && agentResult.logs && agentResult.logs.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Terminal size={18} color="#38bdf8" />
              StoreAgent Execution Trace Logs
            </h2>
            <span className="badge badge-purple">{agentResult.logs.length} Steps Recorded</span>
          </div>
          <div className="card-body" style={{ padding: '1rem 1.25rem', background: '#080c14' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {agentResult.logs.map((log, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.75rem',
                    fontSize: '0.875rem',
                    padding: '0.5rem 0.75rem',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(255, 255, 255, 0.02)',
                    borderLeft: '3px solid #38bdf8',
                  }}
                >
                  <span className={`badge ${getStepBadgeClass(log.step)}`} style={{ minWidth: '100px', justifyContent: 'center' }}>
                    {log.step}
                  </span>
                  <div style={{ color: 'var(--text-main)', flex: 1, fontFamily: 'var(--font-mono)', fontSize: '0.83rem' }}>
                    {log.message}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Standby Card */}
      {!agentResult && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <h2 className="card-title">StoreAgent Evaluation Standby</h2>
            <span className="badge badge-blue">Ready for Execution</span>
          </div>
          <div className="card-body">
            <p style={{ color: 'var(--text-muted)', marginBottom: '1.25rem', fontSize: '0.95rem' }}>
              Click <strong>"Run Store Procurement Agent"</strong> above to trigger autonomous demand forecasting, vendor quote discovery, multi-factor scoring, supplier negotiation, deal validation, and ERP Purchase Order execution across the pharmacy catalogue.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
