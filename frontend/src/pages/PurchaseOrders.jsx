import React, { useEffect, useState } from 'react';
import {
  ShoppingCart,
  RefreshCw,
  AlertTriangle,
  FileText,
  CheckCircle2,
  Clock,
  DollarSign,
  Package,
  ShieldCheck,
  Search,
  Filter,
  Check,
  Send,
  XCircle,
  Truck,
  PlusCircle,
  History,
  ClipboardList,
  AlertCircle,
  Calendar,
  Layers,
  FileSpreadsheet,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function PurchaseOrders() {
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [goodsReceipts, setGoodsReceipts] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Active view tab
  const [activeTab, setActiveTab] = useState('orders'); // 'orders', 'receipts', 'audit'

  // Search and status filter
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Receiving Modal State
  const [receivingPo, setReceivingPo] = useState(null);
  const [receivingFormData, setReceivingFormData] = useState({
    received_quantity: 0,
    batch_number: '',
    expiry_date: '',
    notes: '',
  });
  const [receivingError, setReceivingError] = useState(null);
  const [submittingReceive, setSubmittingReceive] = useState(false);

  // Action loading state
  const [actionLoadingId, setActionLoadingId] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [posRes, receiptsRes, auditRes] = await Promise.all([
        fetch(`${API_BASE}/purchase-orders`),
        fetch(`${API_BASE}/goods-receipts`),
        fetch(`${API_BASE}/audit-logs?limit=50`),
      ]);

      if (!posRes.ok) throw new Error(`HTTP ${posRes.status}: Failed to fetch purchase orders`);
      const posData = await posRes.json();
      setPurchaseOrders(posData);

      if (receiptsRes.ok) {
        const rcptData = await receiptsRes.json();
        setGoodsReceipts(rcptData);
      }

      if (auditRes.ok) {
        const auditData = await auditRes.json();
        setAuditLogs(auditData);
      }
    } catch (err) {
      setError(err.message || 'Failed to connect to backend ERP');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // --- Order Lifecycle Actions ---
  const handleApprovePO = async (poId) => {
    setActionLoadingId(poId);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/purchase-orders/${poId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approver: 'Chief Pharmacist' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Approval failed');

      setSuccessMsg(`PO-#${String(poId).padStart(4, '0')} approved successfully!`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDispatchPO = async (poId) => {
    setActionLoadingId(poId);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/purchase-orders/${poId}/order`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Dispatch failed');

      setSuccessMsg(`PO-#${String(poId).padStart(4, '0')} dispatched to supplier via Simulated Demo Gateway!`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCancelPO = async (poId) => {
    if (!window.confirm(`Are you sure you want to cancel PO-#${String(poId).padStart(4, '0')}?`)) return;
    setActionLoadingId(poId);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/purchase-orders/${poId}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Cancelled by inventory manager' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Cancellation failed');

      setSuccessMsg(`PO-#${String(poId).padStart(4, '0')} cancelled.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoadingId(null);
    }
  };

  // --- Receiving Modal Handlers ---
  const openReceiveModal = (po) => {
    const remaining = Math.max(0, po.quantity - (po.received_quantity || 0));
    const randomBatchSuffix = Math.floor(100 + Math.random() * 900);
    const defaultBatch = `LOT-2026-${po.med_id.toString().padStart(3, '0')}-${randomBatchSuffix}`;
    const defaultExpiry = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    setReceivingPo(po);
    setReceivingFormData({
      received_quantity: remaining,
      batch_number: defaultBatch,
      expiry_date: defaultExpiry,
      notes: 'Physical delivery verified; packaging intact',
    });
    setReceivingError(null);
  };

  const closeReceiveModal = () => {
    setReceivingPo(null);
    setReceivingError(null);
  };

  const handleReceiveSubmit = async (e) => {
    e.preventDefault();
    setReceivingError(null);

    const qty = parseInt(receivingFormData.received_quantity, 10);
    const batch = receivingFormData.batch_number.trim();
    const expiry = receivingFormData.expiry_date.trim();

    if (isNaN(qty) || qty <= 0) {
      setReceivingError('Received Quantity must be a positive integer greater than 0.');
      return;
    }
    if (!batch) {
      setReceivingError('Batch/Lot Number is required for pharmacy audit traceability.');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(expiry)) {
      setReceivingError('Expiry Date must follow YYYY-MM-DD format.');
      return;
    }

    setSubmittingReceive(true);
    try {
      const res = await fetch(`${API_BASE}/purchase-orders/${receivingPo.po_id}/receive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          received_quantity: qty,
          batch_number: batch,
          expiry_date: expiry,
          notes: receivingFormData.notes,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Receiving transaction failed');

      setSuccessMsg(
        `Goods received for PO-#${String(receivingPo.po_id).padStart(4, '0')}: +${qty} units of ${receivingPo.medicine_name} recorded in inventory! (Batch: ${batch})`
      );
      setTimeout(() => setSuccessMsg(null), 6000);
      closeReceiveModal();
      await fetchData();
    } catch (err) {
      setReceivingError(err.message);
    } finally {
      setSubmittingReceive(false);
    }
  };

  // Status Badge Helper
  const getStatusBadge = (status) => {
    switch (status) {
      case 'DRAFT':
        return <span className="badge badge-purple">DRAFT</span>;
      case 'PENDING_APPROVAL':
        return <span className="badge badge-amber"><Clock size={12} /> PENDING APPROVAL</span>;
      case 'APPROVED':
        return <span className="badge badge-blue"><Check size={12} /> APPROVED</span>;
      case 'ORDERED':
        return <span className="badge badge-blue"><Truck size={12} /> ORDERED (IN TRANSIT)</span>;
      case 'PARTIALLY_RECEIVED':
        return <span className="badge badge-amber"><Package size={12} /> PARTIALLY RECEIVED</span>;
      case 'RECEIVED':
      case 'CREATED':
        return <span className="badge badge-green"><CheckCircle2 size={12} /> RECEIVED</span>;
      case 'CANCELLED':
      case 'REJECTED':
        return <span className="badge badge-rose"><XCircle size={12} /> {status}</span>;
      default:
        return <span className="badge badge-blue">{status}</span>;
    }
  };

  // Filtered Orders
  const filteredOrders = purchaseOrders.filter((po) => {
    const matchesSearch =
      (po.medicine_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (po.vendor_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      `PO-#${String(po.po_id).padStart(4, '0')}`.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'ACTIVE') {
      return ['PENDING_APPROVAL', 'APPROVED', 'ORDERED', 'PARTIALLY_RECEIVED'].includes(po.status);
    }
    return po.status === statusFilter;
  });

  // KPI Metrics
  const totalSpend = purchaseOrders.reduce((sum, po) => sum + (Number(po.total_cost) || 0), 0);
  const totalUnitsOrdered = purchaseOrders.reduce((sum, po) => sum + (Number(po.quantity) || 0), 0);
  const totalUnitsReceived = purchaseOrders.reduce((sum, po) => sum + (Number(po.received_quantity) || 0), 0);
  const pendingOrdersCount = purchaseOrders.filter((po) =>
    ['PENDING_APPROVAL', 'APPROVED', 'ORDERED', 'PARTIALLY_RECEIVED'].includes(po.status)
  ).length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <ShoppingCart size={28} color="#10b981" />
            Purchase Orders & Receiving Lifecycle
          </h1>
          <p className="page-subtitle">
            Controlled Procurement Lifecycle: Approval &middot; Dispatch &middot; Verification &middot; Physical Goods Receiving &middot; Audit Trail
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button
            id="btn-refresh-pos"
            onClick={fetchData}
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? 'spinner' : ''} />
            <span>Refresh Ledger</span>
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="toast-success" style={{ marginBottom: '1rem' }}>
          <CheckCircle2 size={18} color="#34d399" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="error-box" style={{ marginBottom: '1.25rem' }}>
          <AlertTriangle size={20} />
          <div>
            <strong>Backend Error:</strong> {error}
          </div>
        </div>
      )}

      {/* KPI Stats Grid */}
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
            <div className="stat-label">Total Procurement Spend</div>
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
            <div className="stat-label">Stock Restocked to ERP</div>
            <div className="stat-value font-mono" style={{ color: '#c084fc' }}>
              {totalUnitsReceived} / {totalUnitsOrdered} units
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
            <Truck size={24} />
          </div>
          <div>
            <div className="stat-label">Active / In-Transit Orders</div>
            <div className="stat-value font-mono" style={{ color: '#fbbf24' }}>
              {pendingOrdersCount} active
            </div>
          </div>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setActiveTab('orders')}
          className={`btn ${activeTab === 'orders' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.5rem 1rem', fontSize: '0.88rem' }}
        >
          <ClipboardList size={16} />
          <span>Purchase Orders Ledger ({purchaseOrders.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('receipts')}
          className={`btn ${activeTab === 'receipts' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.5rem 1rem', fontSize: '0.88rem' }}
        >
          <Package size={16} />
          <span>Goods Receipts History ({goodsReceipts.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`btn ${activeTab === 'audit' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.5rem 1rem', fontSize: '0.88rem' }}
        >
          <History size={16} />
          <span>ERP Audit Trail ({auditLogs.length})</span>
        </button>
      </div>

      {/* TAB 1: PURCHASE ORDERS LEDGER */}
      {activeTab === 'orders' && (
        <div className="card">
          <div className="card-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h2 className="card-title">Order Lifecycle Management</h2>
              <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <ShieldCheck size={14} />
                Strict Non-Auto Restock Guard
              </span>
            </div>

            {/* Search and Filters */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <div style={{ position: 'relative', minWidth: '220px' }}>
                <Search size={15} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Search PO#, medicine, vendor..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="form-input"
                  style={{ paddingLeft: '32px', height: '36px', fontSize: '0.85rem' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '4px' }}>
                {['ALL', 'ACTIVE', 'APPROVED', 'ORDERED', 'RECEIVED'].map((st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`btn btn-sm ${statusFilter === st ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {loading ? (
            <div className="loading-box">
              <div className="spinner" />
              <p>Loading purchase orders from database...</p>
            </div>
          ) : filteredOrders.length === 0 ? (
            <div className="empty-box" id="empty-pos-state">
              <FileText className="empty-icon" />
              <div style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--text-main)' }}>
                No Matching Purchase Orders Found
              </div>
              <p style={{ maxWidth: '480px', fontSize: '0.9rem' }}>
                {purchaseOrders.length === 0
                  ? 'No purchase orders exist in the database. Run the Store Procurement Agent in Agent Control and click "Execute Procurement" to create orders.'
                  : 'No orders match the current search query and status filter.'}
              </p>
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table" id="pos-table">
                <thead>
                  <tr>
                    <th>PO Identifier</th>
                    <th>Medicine</th>
                    <th>Supplier</th>
                    <th>Ordered Qty</th>
                    <th>Received Qty</th>
                    <th>Agreed Rate</th>
                    <th>Total Spend</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'center' }}>Lifecycle Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((po) => {
                    const remaining = Math.max(0, po.quantity - (po.received_quantity || 0));
                    const isProcessing = actionLoadingId === po.po_id;

                    return (
                      <tr key={po.po_id} id={`po-row-${po.po_id}`}>
                        <td className="font-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                          PO-#{String(po.po_id).padStart(4, '0')}
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{po.medicine_name || `Med #${po.med_id}`}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            Lead time: {po.delivery_days}d SLA
                          </div>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                            {po.vendor_name || `Vendor #${po.vendor_id}`}
                          </span>
                        </td>
                        <td className="font-mono" style={{ fontWeight: 700 }}>
                          {po.quantity} units
                        </td>
                        <td>
                          <div className="font-mono" style={{ fontWeight: 700, color: po.received_quantity > 0 ? '#34d399' : 'var(--text-muted)' }}>
                            {po.received_quantity || 0} units
                          </div>
                          {remaining > 0 && po.status !== 'CANCELLED' && (
                            <div style={{ fontSize: '0.72rem', color: '#fbbf24' }}>
                              ({remaining} remaining)
                            </div>
                          )}
                        </td>
                        <td className="font-mono" style={{ color: '#38bdf8', fontWeight: 600 }}>
                          ${Number(po.unit_price).toFixed(2)}/u
                        </td>
                        <td className="font-mono" style={{ fontWeight: 800, color: '#34d399', fontSize: '0.95rem' }}>
                          ${Number(po.total_cost).toFixed(2)}
                        </td>
                        <td>{getStatusBadge(po.status)}</td>
                        <td style={{ textAlign: 'center' }}>
                          <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                            {/* PENDING APPROVAL -> Approve */}
                            {po.status === 'PENDING_APPROVAL' && (
                              <button
                                onClick={() => handleApprovePO(po.po_id)}
                                className="btn btn-sm btn-primary"
                                disabled={isProcessing}
                                title="Approve Purchase Order"
                              >
                                <Check size={13} />
                                <span>Approve</span>
                              </button>
                            )}

                            {/* APPROVED -> Order / Dispatch */}
                            {po.status === 'APPROVED' && (
                              <button
                                onClick={() => handleDispatchPO(po.po_id)}
                                className="btn btn-sm"
                                style={{ background: '#0284c7', color: '#fff' }}
                                disabled={isProcessing}
                                title="Send Electronic PO to Supplier"
                              >
                                <Send size={13} />
                                <span>Dispatch</span>
                              </button>
                            )}

                            {/* ORDERED / PARTIALLY_RECEIVED -> Receive Goods */}
                            {['ORDERED', 'PARTIALLY_RECEIVED', 'APPROVED'].includes(po.status) && (
                              <button
                                onClick={() => openReceiveModal(po)}
                                className="btn btn-sm"
                                style={{ background: '#059669', color: '#fff' }}
                                disabled={isProcessing}
                                title="Record Goods Receipt & Verify Stock"
                              >
                                <Package size={13} />
                                <span>Receive Goods</span>
                              </button>
                            )}

                            {/* Active orders can be cancelled */}
                            {['PENDING_APPROVAL', 'APPROVED', 'ORDERED'].includes(po.status) && (
                              <button
                                onClick={() => handleCancelPO(po.po_id)}
                                className="btn btn-sm btn-secondary"
                                style={{ color: '#fb7185', borderColor: 'rgba(244,63,94,0.3)' }}
                                disabled={isProcessing}
                                title="Cancel Order"
                              >
                                <XCircle size={13} />
                                <span>Cancel</span>
                              </button>
                            )}

                            {/* Terminal status */}
                            {['RECEIVED', 'CREATED'].includes(po.status) && (
                              <span style={{ fontSize: '0.78rem', color: '#34d399', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                <CheckCircle2 size={13} /> Fulfilled
                              </span>
                            )}
                            {['CANCELLED', 'REJECTED'].includes(po.status) && (
                              <span style={{ fontSize: '0.78rem', color: '#fb7185' }}>
                                Closed
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: GOODS RECEIPTS HISTORY */}
      {activeTab === 'receipts' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Physical Goods Receipts Ledger ({goodsReceipts.length})</h2>
            <span className="badge badge-green">Batch-Level Verified Records</span>
          </div>

          {goodsReceipts.length === 0 ? (
            <div className="empty-box">
              <Package className="empty-icon" />
              <div style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--text-main)' }}>
                No Goods Receipts Recorded Yet
              </div>
              <p style={{ maxWidth: '480px', fontSize: '0.9rem' }}>
                Goods receipts are recorded when incoming pharmacy shipments are physically inspected and verified at the warehouse. Use the "Receive Goods" action on dispatched purchase orders to record stock arrival.
              </p>
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Receipt ID</th>
                    <th>PO Ref</th>
                    <th>Medicine</th>
                    <th>Supplier</th>
                    <th>Received Quantity</th>
                    <th>Batch / Lot Number</th>
                    <th>Manufacturer Expiry</th>
                    <th>Discrepancy</th>
                    <th>Received At</th>
                  </tr>
                </thead>
                <tbody>
                  {goodsReceipts.map((gr) => (
                    <tr key={gr.receipt_id}>
                      <td className="font-mono" style={{ fontWeight: 700, color: '#34d399' }}>
                        RC-#{String(gr.receipt_id).padStart(4, '0')}
                      </td>
                      <td className="font-mono" style={{ color: '#38bdf8' }}>
                        PO-#{String(gr.po_id).padStart(4, '0')}
                      </td>
                      <td style={{ fontWeight: 600 }}>{gr.medicine_name || `Med #${gr.med_id}`}</td>
                      <td>{gr.vendor_name || `Vendor #${gr.vendor_id}`}</td>
                      <td className="font-mono" style={{ fontWeight: 800, color: '#34d399' }}>
                        +{gr.received_qty} units
                      </td>
                      <td className="font-mono" style={{ fontWeight: 600, color: '#c084fc' }}>
                        {gr.batch_number}
                      </td>
                      <td className="font-mono">{gr.expiry_date}</td>
                      <td>
                        {gr.discrepancy_qty === 0 ? (
                          <span className="badge badge-green">Exact Match</span>
                        ) : gr.discrepancy_qty > 0 ? (
                          <span className="badge badge-amber">+{gr.discrepancy_qty} Extra</span>
                        ) : (
                          <span className="badge badge-rose">{gr.discrepancy_qty} Shortage</span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(gr.received_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: AUDIT TRAIL */}
      {activeTab === 'audit' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">ERP Procurement Audit Trail (Last {auditLogs.length} events)</h2>
            <span className="badge badge-purple">Immutable Ledger Trail</span>
          </div>

          {auditLogs.length === 0 ? (
            <div className="empty-box">
              <History className="empty-icon" />
              <div style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--text-main)' }}>
                No Audit Log Events Recorded Yet
              </div>
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Log ID</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Details</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.map((log) => (
                    <tr key={log.log_id}>
                      <td className="font-mono" style={{ color: 'var(--text-dim)' }}>
                        #{log.log_id}
                      </td>
                      <td>
                        <span className="badge badge-blue font-mono" style={{ fontWeight: 700 }}>
                          {log.action}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontWeight: 600 }}>{log.entity_type}</span>
                        {log.entity_id && (
                          <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: '4px' }}>
                            (#{log.entity_id})
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.88rem', color: 'var(--text-main)' }}>{log.details}</td>
                      <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* GOODS RECEIVING INSPECTION MODAL */}
      {receivingPo && (
        <div className="modal-backdrop" onClick={closeReceiveModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '540px' }}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Package size={20} color="#10b981" />
                  Goods Receipt & Stock Verification
                </h3>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  PO-#{String(receivingPo.po_id).padStart(4, '0')} &middot; {receivingPo.medicine_name} &middot; {receivingPo.vendor_name}
                </div>
              </div>
              <button onClick={closeReceiveModal} className="btn-close">
                &times;
              </button>
            </div>

            {receivingError && (
              <div className="error-box" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertTriangle size={18} />
                <span>{receivingError}</span>
              </div>
            )}

            <form onSubmit={handleReceiveSubmit} style={{ padding: '1.25rem 1.5rem' }}>
              {/* Order Info Card */}
              <div
                style={{
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.85rem 1rem',
                  marginBottom: '1.25rem',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: '0.5rem',
                  fontSize: '0.82rem',
                }}
              >
                <div>
                  <div style={{ color: 'var(--text-dim)' }}>Ordered Quantity</div>
                  <div className="font-mono" style={{ fontWeight: 800, fontSize: '1rem', color: '#38bdf8' }}>
                    {receivingPo.quantity} units
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-dim)' }}>Already Received</div>
                  <div className="font-mono" style={{ fontWeight: 800, fontSize: '1rem', color: '#34d399' }}>
                    {receivingPo.received_quantity || 0} units
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-dim)' }}>Pending Arrival</div>
                  <div className="font-mono" style={{ fontWeight: 800, fontSize: '1rem', color: '#fbbf24' }}>
                    {Math.max(0, receivingPo.quantity - (receivingPo.received_quantity || 0))} units
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Verified Received Quantity <span style={{ color: '#fb7185' }}>*</span>
                </label>
                <input
                  type="number"
                  min="1"
                  value={receivingFormData.received_quantity}
                  onChange={(e) =>
                    setReceivingFormData({ ...receivingFormData, received_quantity: e.target.value })
                  }
                  className="form-input font-mono"
                  style={{ fontSize: '1rem', fontWeight: 700 }}
                  required
                />
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '3px' }}>
                  Only physical verified units entered here will be added to available inventory.
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Batch / Lot Identifier <span style={{ color: '#fb7185' }}>*</span>
                </label>
                <input
                  type="text"
                  value={receivingFormData.batch_number}
                  onChange={(e) =>
                    setReceivingFormData({ ...receivingFormData, batch_number: e.target.value })
                  }
                  placeholder="e.g. LOT-2026-PARA-042"
                  className="form-input font-mono"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  Manufacturer Expiry Date <span style={{ color: '#fb7185' }}>*</span>
                </label>
                <input
                  type="date"
                  value={receivingFormData.expiry_date}
                  onChange={(e) =>
                    setReceivingFormData({ ...receivingFormData, expiry_date: e.target.value })
                  }
                  className="form-input font-mono"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Receiving Notes / Quality Inspection</label>
                <input
                  type="text"
                  value={receivingFormData.notes}
                  onChange={(e) =>
                    setReceivingFormData({ ...receivingFormData, notes: e.target.value })
                  }
                  placeholder="e.g. Seal intact, cold-chain verified, no damaged packs"
                  className="form-input"
                />
              </div>

              <div className="modal-footer" style={{ padding: '1rem 0 0', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" onClick={closeReceiveModal} className="btn btn-secondary" disabled={submittingReceive}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ background: '#059669', borderColor: '#059669' }}
                  disabled={submittingReceive}
                >
                  {submittingReceive ? (
                    <>
                      <RefreshCw size={16} className="spinner" />
                      <span>Writing to ERP...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} />
                      <span>Confirm Receipt & Update Inventory</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
