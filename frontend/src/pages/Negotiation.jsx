import React, { useEffect, useState } from 'react';
import {
  MessageSquare,
  Bot,
  Users,
  Play,
  CheckCircle2,
  AlertCircle,
  TrendingDown,
  DollarSign,
  Clock,
  Package,
  Layers,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  ShoppingCart,
  ShieldCheck,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function Negotiation() {
  const [loading, setLoading] = useState(false);
  const [executingMedId, setExecutingMedId] = useState(null);
  const [agentData, setAgentData] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [execSuccessMsg, setExecSuccessMsg] = useState(null);

  const fetchNegotiationData = async () => {
    setLoading(true);
    setErrorMsg(null);
    setExecSuccessMsg(null);
    try {
      const res = await fetch(`${API_BASE}/procurement/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to execute negotiation`);
      }
      const data = await res.json();
      setAgentData(data);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to connect to backend negotiation engine');
    } finally {
      setLoading(false);
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

      setAgentData((prev) => {
        if (!prev) return prev;
        const updatedMeds = prev.medicines.map((m) => {
          if (m.med_id === medicineId) {
            return {
              ...m,
              current_stock: execData.inventory?.after ?? m.current_stock,
              po: execData.po,
              execution_result: execData.execution_result,
            };
          }
          return m;
        });
        return {
          ...prev,
          medicines: updatedMeds,
        };
      });

      setExecSuccessMsg(`Purchase Order ${execData.po?.po_number || `PO-#${execData.po?.po_id}`} committed to SQLite ERP! Stock restocked: ${execData.inventory?.before} → ${execData.inventory?.after}.`);
    } catch (err) {
      setErrorMsg(err.message || 'Execution failed');
    } finally {
      setExecutingMedId(null);
    }
  };

  useEffect(() => {
    fetchNegotiationData();
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <MessageSquare size={28} color="#f59e0b" />
            Autonomous Adaptive Negotiation
          </h1>
          <p className="page-subtitle">
            Multi-Round Bargaining Protocol, Concession Engine & ERP Write-Back (Phase 6)
          </p>
        </div>
        <div>
          <button
            id="btn-trigger-negotiation"
            onClick={fetchNegotiationData}
            className="btn btn-primary"
            disabled={loading}
            style={{ padding: '0.75rem 1.5rem', fontSize: '0.95rem' }}
          >
            <Play size={18} fill="currentColor" />
            <span>{loading ? 'Negotiating with Vendors...' : 'Run Negotiation Protocol'}</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="error-box">
          <AlertCircle size={20} />
          <div>
            <strong>Error:</strong> {errorMsg}
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
      {agentData && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
              <CheckCircle2 size={24} />
            </div>
            <div>
              <div className="stat-label">Negotiations Agreed</div>
              <div className="stat-value" style={{ color: '#34d399' }}>
                {agentData.negotiation_accepted_count || agentData.medicines?.filter((m) => m.negotiation?.status === 'ACCEPTED').length || 0} / {agentData.medicines?.length || 0}
              </div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(2, 132, 199, 0.15)', color: '#38bdf8' }}>
              <TrendingDown size={24} />
            </div>
            <div>
              <div className="stat-label">Total Procurement Savings</div>
              <div className="stat-value" style={{ color: '#38bdf8' }}>
                ${agentData.medicines
                  ?.reduce((sum, m) => sum + (m.best_offer?.savings || 0), 0)
                  .toFixed(2)}
              </div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
              <Clock size={24} />
            </div>
            <div>
              <div className="stat-label">Round Limit SLA</div>
              <div className="stat-value" style={{ color: '#fbbf24' }}>Max 2 Rounds</div>
            </div>
          </div>
        </div>
      )}

      {/* Negotiation Transcripts Per Medicine */}
      {agentData && agentData.medicines && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {agentData.medicines.map((med) => {
            const neg = med.negotiation || {};
            const history = med.negotiation_history || neg.history || [];
            const best = med.best_offer || neg.best_offer;
            const vendorName = med.selected_vendor?.vendor_name || neg.vendor_name || 'Selected Vendor';
            const isAccepted = med.decision === 'ACCEPT' && med.validation_result?.valid;
            const hasPO = med.po && med.po.po_id;

            return (
              <div key={med.med_id} className="card" id={`negotiation-card-${med.med_id}`}>
                {/* Header Summary */}
                <div className="card-header" style={{ background: 'rgba(255, 255, 255, 0.02)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <Package size={20} color="#38bdf8" />
                    <div>
                      <h2 className="card-title" style={{ display: 'inline', marginRight: '0.5rem' }}>
                        {med.name}
                      </h2>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        &bull; Negotiating with <strong style={{ color: 'var(--text-main)' }}>{vendorName}</strong>
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span className="badge badge-purple font-mono">
                      Round: {neg.round || 2} / 2
                    </span>
                    {neg.status === 'ACCEPTED' ? (
                      <span className="badge badge-green" style={{ fontWeight: 800 }}>
                        <CheckCircle2 size={13} />
                        AGREED & ACCEPTED
                      </span>
                    ) : (
                      <span className="badge badge-rose">
                        <AlertCircle size={13} />
                        {neg.status || 'INACTIVE'}
                      </span>
                    )}
                  </div>
                </div>

                <div className="card-body">
                  {/* Financial Terms Card */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                      gap: '1rem',
                      background: 'var(--bg-subtle)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      padding: '1rem 1.25rem',
                      marginBottom: '1.5rem',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>INITIAL QUOTE</div>
                      <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                        ${(neg.initial_price || med.selected_vendor?.base_price || 0).toFixed(2)}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>AGENT TARGET (-10%)</div>
                      <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: 700, color: '#38bdf8' }}>
                        ${(neg.target_price || 0).toFixed(2)}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>FINAL BEST OFFER</div>
                      <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: 800, color: '#34d399' }}>
                        ${best ? best.unit_price.toFixed(2) : '-'}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>ORDER COMMITMENT</div>
                      <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)' }}>
                        ${best ? best.total_cost.toFixed(2) : '-'} ({best ? best.quantity : med.required_qty} u)
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>ACHIEVED SAVINGS</div>
                      <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: 800, color: '#34d399' }}>
                        +${best ? best.savings.toFixed(2) : '0.00'} ({best ? best.discount_pct : 0}%)
                      </div>
                    </div>
                  </div>

                  {/* Phase 5 Deal Validation Checklist & Phase 6 Execution Button */}
                  {med.validation_result && med.validation_result.checks && (
                    <div
                      style={{
                        background: 'var(--bg-subtle)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem 1.25rem',
                        marginBottom: '1.5rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                          Phase 5 Multi-Constraint Deal Validation
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <span className={`badge ${med.validation_result.valid ? 'badge-green' : 'badge-rose'}`} style={{ fontWeight: 800 }}>
                            {med.validation_result.valid ? '✓ ALL 7 CONSTRAINTS PASSED' : '✗ VALIDATION FAILED'}
                          </span>
                          {med.decision && (
                            <span className={`badge ${med.decision === 'ACCEPT' ? 'badge-green' : med.decision === 'SWITCH_VENDOR' ? 'badge-amber' : 'badge-rose'}`} style={{ fontWeight: 800 }}>
                              FINAL DECISION: {med.decision}
                            </span>
                          )}
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem', marginBottom: '0.75rem' }}>
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

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          <strong>Reason:</strong> {med.decision_reason || med.validation_result.reason}
                        </div>

                        {/* Phase 6 CTA Button */}
                        {isAccepted && !hasPO && (
                          <button
                            id={`btn-execute-neg-po-${med.med_id}`}
                            onClick={() => handleExecuteProcurement(med.med_id)}
                            className="btn btn-primary"
                            disabled={executingMedId === med.med_id}
                            style={{ padding: '0.45rem 0.9rem', fontSize: '0.8rem', background: '#059669', borderColor: '#10b981' }}
                          >
                            <ShoppingCart size={14} />
                            <span>{executingMedId === med.med_id ? 'Writing to ERP...' : 'Execute PO in ERP'}</span>
                          </button>
                        )}
                        {hasPO && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.4)', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.65rem' }}>
                            <ShieldCheck size={15} color="#34d399" />
                            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#34d399' }}>
                              PO Created: {med.po.po_number || `PO-#${med.po.po_id}`} (Stock: {med.current_stock})
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Transcript Chat Stream */}
                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.25rem' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '1rem' }}>
                      Bargaining Transcript & Rationale Log ({history.length} Turns)
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      {history.map((turn, idx) => {
                        const isAgent = turn.speaker === 'STORE_AGENT';
                        return (
                          <div
                            key={idx}
                            style={{
                              display: 'flex',
                              flexDirection: 'column',
                              alignItems: isAgent ? 'flex-start' : 'flex-end',
                            }}
                          >
                            <div
                              style={{
                                maxWidth: '75%',
                                minWidth: '280px',
                                background: isAgent ? 'rgba(2, 132, 199, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                                border: `1px solid ${isAgent ? 'rgba(2, 132, 199, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                                borderRadius: 'var(--radius-md)',
                                padding: '0.875rem 1.125rem',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, fontSize: '0.85rem' }}>
                                  {isAgent ? (
                                    <>
                                      <Bot size={15} color="#38bdf8" />
                                      <span style={{ color: '#38bdf8' }}>STORE AGENT</span>
                                    </>
                                  ) : (
                                    <>
                                      <Users size={15} color="#fbbf24" />
                                      <span style={{ color: '#fbbf24' }}>{vendorName.toUpperCase()}</span>
                                    </>
                                  )}
                                </div>
                                <span className={`badge ${turn.action === 'ACCEPT' ? 'badge-green' : turn.action === 'COUNTER' ? 'badge-purple' : 'badge-blue'}`}>
                                  {turn.action} &bull; ${turn.price?.toFixed(2)}
                                </span>
                              </div>

                              <div style={{ fontSize: '0.9rem', color: 'var(--text-main)', lineHeight: '1.4' }}>
                                {turn.message}
                              </div>

                              {turn.reason && (
                                <div style={{ marginTop: '0.5rem', fontSize: '0.775rem', color: 'var(--text-muted)', borderTop: '1px dashed rgba(255,255,255,0.1)', paddingTop: '0.35rem' }}>
                                  <strong style={{ color: 'var(--text-dim)' }}>Rationale:</strong> {turn.reason}
                                </div>
                              )}
                            </div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '2px', padding: '0 4px' }}>
                              Round {turn.round} &bull; {isAgent ? 'Agent Proposal' : 'Vendor Response'}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Standby View if No Data */}
      {!agentData && !loading && (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
            <MessageSquare size={40} color="#f59e0b" style={{ margin: '0 auto 1rem' }} />
            <h2 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Negotiation Engine Ready</h2>
            <p style={{ color: 'var(--text-muted)', maxWidth: '500px', margin: '0 auto 1.5rem' }}>
              Click <strong>"Run Negotiation Protocol"</strong> to initiate autonomous bargaining with selected suppliers across the 3 hero medicines.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
