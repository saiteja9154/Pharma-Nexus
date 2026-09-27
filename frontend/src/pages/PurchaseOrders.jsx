import React, { useEffect, useState } from 'react';
import { ShoppingCart, RefreshCw, AlertTriangle, FileText, CheckCircle2, Clock, DollarSign, TrendingDown, Package, ShieldCheck } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function PurchaseOrders() {
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPurchaseOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/purchase-orders`);
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();
      setPurchaseOrders(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch purchase orders from FastAPI backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPurchaseOrders();
  }, []);

  const totalSpend = purchaseOrders.reduce((sum, po) => sum + (Number(po.total_cost) || 0), 0);
  const totalUnits = purchaseOrders.reduce((sum, po) => sum + (Number(po.quantity) || 0), 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <ShoppingCart size={28} color="#10b981" />
            Purchase Orders
          </h1>
          <p className="page-subtitle">
            Autonomous Restocking & Final Negotiated ERP Purchase Order Ledger (Phase 6)
          </p>
        </div>
        <button
          id="btn-refresh-pos"
          onClick={fetchPurchaseOrders}
          className="btn btn-secondary"
          disabled={loading}
        >
          <RefreshCw size={16} className={loading ? 'spinner' : ''} />
          <span>Refresh Orders</span>
        </button>
      </div>

      {error && (
        <div className="error-box">
          <AlertTriangle size={20} />
          <div>
            <strong>Error connecting to FastAPI backend:</strong> {error}
          </div>
        </div>
      )}

      {/* KPI Stats Banner */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
            <FileText size={24} />
          </div>
          <div>
            <div className="stat-label">Total Purchase Orders</div>
            <div className="stat-value" style={{ color: '#34d399' }}>{purchaseOrders.length}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
            <DollarSign size={24} />
          </div>
          <div>
            <div className="stat-label">Total ERP Spend</div>
            <div className="stat-value font-mono" style={{ color: '#38bdf8' }}>
              ${totalSpend.toFixed(2)}
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc' }}>
            <Package size={24} />
          </div>
          <div>
            <div className="stat-label">Total Restocked Units</div>
            <div className="stat-value font-mono" style={{ color: '#c084fc' }}>
              {totalUnits} units
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="card">
          <div className="loading-box">
            <div className="spinner" />
            <p>Loading purchase orders from database...</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Recorded Purchase Orders ({purchaseOrders.length})</h2>
            <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <ShieldCheck size={14} />
              SQLite ERP Ledger Committed
            </span>
          </div>

          {purchaseOrders.length === 0 ? (
            <div className="empty-box" id="empty-pos-state">
              <FileText className="empty-icon" />
              <div style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--text-main)' }}>
                No Purchase Orders Executed Yet
              </div>
              <p style={{ maxWidth: '480px', fontSize: '0.9rem' }}>
                The purchase orders ledger is currently empty. Run the <strong>Store Procurement Agent</strong> in <em>Agent Control</em> and click <strong>"Execute Procurement & Write to ERP"</strong> to finalize agreed restock orders into the SQLite ERP ledger.
              </p>
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table" id="pos-table">
                <thead>
                  <tr>
                    <th>PO ID</th>
                    <th>Medicine</th>
                    <th>Vendor</th>
                    <th>Quantity</th>
                    <th>Final Negotiated Price</th>
                    <th>Total Commitment</th>
                    <th>Delivery SLA</th>
                    <th>ERP Status</th>
                  </tr>
                </thead>
                <tbody>
                  {purchaseOrders.map((po) => (
                    <tr key={po.po_id} id={`po-row-${po.po_id}`}>
                      <td className="font-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                        PO-#{String(po.po_id).padStart(4, '0')}
                      </td>
                      <td style={{ fontWeight: 600 }}>{po.medicine_name || `Med #${po.med_id}`}</td>
                      <td>
                        <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                          {po.vendor_name || `Vendor #${po.vendor_id}`}
                        </span>
                      </td>
                      <td className="font-mono" style={{ fontWeight: 700 }}>
                        {po.quantity} units
                      </td>
                      <td className="font-mono" style={{ color: '#38bdf8', fontWeight: 600 }}>
                        ${Number(po.unit_price).toFixed(2)}/u
                      </td>
                      <td className="font-mono" style={{ fontWeight: 800, color: '#34d399', fontSize: '0.95rem' }}>
                        ${Number(po.total_cost).toFixed(2)}
                      </td>
                      <td>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <Clock size={14} color="var(--text-muted)" />
                          {po.delivery_days} days
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-green" style={{ fontWeight: 700 }}>
                          <CheckCircle2 size={12} />
                          {po.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
