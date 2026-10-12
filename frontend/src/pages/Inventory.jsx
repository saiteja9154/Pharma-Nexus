import React, { useEffect, useState } from 'react';
import {
  Package,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Clock,
  Edit3,
  X,
  Save,
  Plus,
  Search,
  Layers,
  Calendar,
  Filter,
  ShieldAlert,
  ArrowUpDown,
  Boxes,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function Inventory() {
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Filters & Search
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL' | 'REORDER' | 'ADEQUATE' | 'EXPIRING'

  // Batches Modal State
  const [viewingBatchesMed, setViewingBatchesMed] = useState(null);
  const [batches, setBatches] = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [batchesError, setBatchesError] = useState(null);

  // Edit Modal State
  const [editingMed, setEditingMed] = useState(null);
  const [editFormData, setEditFormData] = useState({
    current_stock: 0,
    reorder_point: 0,
    daily_sales: 0,
    lead_time_days: 0,
    expiry_date: '',
  });
  const [editFormError, setEditFormError] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

  // Add Medicine Modal State
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [addFormData, setAddFormData] = useState({
    name: '',
    current_stock: 0,
    reorder_point: 0,
    daily_sales: 0,
    lead_time_days: 0,
    expiry_date: '',
  });
  const [addFormError, setAddFormError] = useState(null);
  const [savingAdd, setSavingAdd] = useState(false);

  const fetchInventory = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/inventory`);
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();
      setInventory(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch inventory from FastAPI backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory();
  }, []);

  // View Batches Handler
  const openBatchesModal = async (med) => {
    setViewingBatchesMed(med);
    setLoadingBatches(true);
    setBatchesError(null);
    try {
      const res = await fetch(`${API_BASE}/inventory/${med.med_id}/batches`);
      if (!res.ok) {
        throw new Error(`Failed to load batches: ${res.statusText}`);
      }
      const data = await res.json();
      setBatches(data);
    } catch (err) {
      setBatchesError(err.message || 'Failed to fetch batch records');
    } finally {
      setLoadingBatches(false);
    }
  };

  const closeBatchesModal = () => {
    setViewingBatchesMed(null);
    setBatches([]);
    setBatchesError(null);
  };

  // Edit Modal Handlers
  const openEditModal = (item) => {
    setEditingMed(item);
    setEditFormData({
      current_stock: item.current_stock,
      reorder_point: item.reorder_point,
      daily_sales: item.daily_sales,
      lead_time_days: item.lead_time_days,
      expiry_date: item.expiry_date,
    });
    setEditFormError(null);
  };

  const closeEditModal = () => {
    setEditingMed(null);
    setEditFormError(null);
  };

  const handleEditInputChange = (e) => {
    const { name, value } = e.target;
    setEditFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleEditSave = async (e) => {
    e.preventDefault();
    setEditFormError(null);

    const currentStock = parseInt(editFormData.current_stock, 10);
    const reorderPoint = parseInt(editFormData.reorder_point, 10);
    const dailySales = parseInt(editFormData.daily_sales, 10);
    const leadTimeDays = parseInt(editFormData.lead_time_days, 10);
    const expiryDate = editFormData.expiry_date.trim();

    if (isNaN(currentStock) || currentStock < 0) {
      setEditFormError('Current Stock must be a non-negative integer (>= 0).');
      return;
    }
    if (isNaN(reorderPoint) || reorderPoint < 0) {
      setEditFormError('Reorder Point must be a non-negative integer (>= 0).');
      return;
    }
    if (isNaN(dailySales) || dailySales < 0) {
      setEditFormError('Daily Sales must be a non-negative integer (>= 0).');
      return;
    }
    if (isNaN(leadTimeDays) || leadTimeDays < 0) {
      setEditFormError('Lead Time must be a non-negative integer (>= 0).');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(expiryDate)) {
      setEditFormError('Expiry Date must follow YYYY-MM-DD format.');
      return;
    }

    setSavingEdit(true);
    try {
      const res = await fetch(`${API_BASE}/inventory/${editingMed.med_id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          current_stock: currentStock,
          reorder_point: reorderPoint,
          daily_sales: dailySales,
          lead_time_days: leadTimeDays,
          expiry_date: expiryDate,
        }),
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Failed to update inventory record');
      }

      setSuccessMsg(`Successfully updated ${editingMed.name} master data in SQLite ERP.`);
      setTimeout(() => setSuccessMsg(null), 5000);
      closeEditModal();
      await fetchInventory();
    } catch (err) {
      setEditFormError(err.message || 'Error saving master data to backend.');
    } finally {
      setSavingEdit(false);
    }
  };

  // Add Medicine Modal Handlers
  const openAddModal = () => {
    setAddFormData({
      name: '',
      current_stock: 0,
      reorder_point: 0,
      daily_sales: 0,
      lead_time_days: 0,
      expiry_date: new Date(Date.now() + 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    });
    setAddFormError(null);
    setIsAddOpen(true);
  };

  const closeAddModal = () => {
    setIsAddOpen(false);
    setAddFormError(null);
  };

  const handleAddInputChange = (e) => {
    const { name, value } = e.target;
    setAddFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleAddSave = async (e) => {
    e.preventDefault();
    setAddFormError(null);

    const name = addFormData.name.trim();
    const currentStock = parseInt(addFormData.current_stock, 10);
    const reorderPoint = parseInt(addFormData.reorder_point, 10);
    const dailySales = parseInt(addFormData.daily_sales, 10);
    const leadTimeDays = parseInt(addFormData.lead_time_days, 10);
    const expiryDate = addFormData.expiry_date.trim();

    if (!name) {
      setAddFormError('Medicine name is required.');
      return;
    }
    if (isNaN(currentStock) || currentStock < 0) {
      setAddFormError('Current Stock must be a non-negative integer (>= 0).');
      return;
    }
    if (isNaN(reorderPoint) || reorderPoint < 0) {
      setAddFormError('Reorder Point must be a non-negative integer (>= 0).');
      return;
    }
    if (isNaN(dailySales) || dailySales < 0) {
      setAddFormError('Daily Sales must be a non-negative integer (>= 0).');
      return;
    }
    if (isNaN(leadTimeDays) || leadTimeDays < 0) {
      setAddFormError('Lead Time must be a non-negative integer (>= 0).');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(expiryDate)) {
      setAddFormError('Expiry Date must follow YYYY-MM-DD format.');
      return;
    }

    setSavingAdd(true);
    try {
      const res = await fetch(`${API_BASE}/inventory`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          current_stock: currentStock,
          reorder_point: reorderPoint,
          daily_sales: dailySales,
          lead_time_days: leadTimeDays,
          expiry_date: expiryDate,
        }),
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Failed to add new medicine');
      }

      setSuccessMsg(`Successfully added new medicine "${result.medicine?.name || name}" (ID: #${result.medicine?.med_id}) to SQLite ERP.`);
      setTimeout(() => setSuccessMsg(null), 5000);
      closeAddModal();
      await fetchInventory();
    } catch (err) {
      setAddFormError(err.message || 'Error creating new medicine record.');
    } finally {
      setSavingAdd(false);
    }
  };

  // Helper date calculations
  const nowMs = Date.now();
  const getDaysUntilExpiry = (expiryStr) => {
    if (!expiryStr) return 999;
    const diff = new Date(expiryStr).getTime() - nowMs;
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  };

  // KPI Calculations
  const totalMeds = inventory.length;
  const reorderCount = inventory.filter((item) => item.current_stock <= item.reorder_point).length;
  const expiringSoonCount = inventory.filter((item) => getDaysUntilExpiry(item.expiry_date) <= 90).length;
  const totalStockUnits = inventory.reduce((sum, item) => sum + (item.current_stock || 0), 0);

  // Filtered List
  const filteredInventory = inventory.filter((item) => {
    // Search match
    const q = searchTerm.toLowerCase().trim();
    const matchesSearch =
      !q ||
      item.name.toLowerCase().includes(q) ||
      String(item.med_id).includes(q);

    if (!matchesSearch) return false;

    // Status Filter
    const isLow = item.current_stock <= item.reorder_point;
    const daysLeft = getDaysUntilExpiry(item.expiry_date);
    const isExpiring = daysLeft <= 90;

    if (statusFilter === 'REORDER') return isLow;
    if (statusFilter === 'ADEQUATE') return !isLow;
    if (statusFilter === 'EXPIRING') return isExpiring;
    return true; // 'ALL'
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Package size={28} color="#38bdf8" />
            Inventory & Lot Management
          </h1>
          <p className="page-subtitle">
            Real-time stock on hand, reorder thresholds, batch lots, and expiry shelf-life monitoring
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            id="btn-add-medicine"
            onClick={openAddModal}
            className="btn btn-primary"
          >
            <Plus size={16} />
            <span>Add Medicine</span>
          </button>
          <button
            id="btn-refresh-inventory"
            onClick={fetchInventory}
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? 'spinner' : ''} />
            <span>Refresh Stock</span>
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="toast-success">
          <CheckCircle size={18} color="#34d399" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="error-box">
          <AlertTriangle size={20} />
          <div>
            <strong>Error connecting to FastAPI backend:</strong> {error}
            <div style={{ fontSize: '0.85rem', marginTop: '4px' }}>
              Ensure the FastAPI backend is running at <code>http://127.0.0.1:8000</code>.
            </div>
          </div>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
            <Package size={24} />
          </div>
          <div>
            <div className="stat-label">Catalog Medicines</div>
            <div className="stat-value" style={{ color: '#38bdf8' }}>
              {totalMeds} Active
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(251, 113, 133, 0.15)', color: '#fb7185' }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <div className="stat-label">Stockout Warnings</div>
            <div className="stat-value" style={{ color: reorderCount > 0 ? '#fb7185' : '#34d399' }}>
              {reorderCount} Need Reorder
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
            <Calendar size={24} />
          </div>
          <div>
            <div className="stat-label">Expiring &le; 90 Days</div>
            <div className="stat-value" style={{ color: expiringSoonCount > 0 ? '#fbbf24' : '#34d399' }}>
              {expiringSoonCount} Batches
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(52, 211, 153, 0.15)', color: '#34d399' }}>
            <Boxes size={24} />
          </div>
          <div>
            <div className="stat-label">Total Stock Units</div>
            <div className="stat-value" style={{ color: '#34d399' }}>
              {totalStockUnits.toLocaleString()} Units
            </div>
          </div>
        </div>
      </div>

      {/* Search and Filters Toolbar */}
      <div
        className="card"
        style={{
          padding: '0.85rem 1.25rem',
          marginBottom: '1.25rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: '1 1 300px', maxWidth: '420px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search
              size={16}
              color="var(--text-muted)"
              style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              id="inventory-search-input"
              type="text"
              placeholder="Search by medicine name or ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="form-input"
              style={{ paddingLeft: '32px', height: '36px', fontSize: '0.85rem' }}
            />
          </div>
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="btn btn-secondary btn-sm"
              title="Clear search"
            >
              Clear
            </button>
          )}
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setStatusFilter('ALL')}
            className={`btn btn-sm ${statusFilter === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
          >
            All ({inventory.length})
          </button>
          <button
            onClick={() => setStatusFilter('REORDER')}
            className={`btn btn-sm ${statusFilter === 'REORDER' ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              fontSize: '0.8rem',
              padding: '0.35rem 0.75rem',
              color: statusFilter === 'REORDER' ? '#fff' : '#fb7185',
              borderColor: statusFilter === 'REORDER' ? 'transparent' : 'rgba(251, 113, 133, 0.4)',
            }}
          >
            Reorder Needed ({reorderCount})
          </button>
          <button
            onClick={() => setStatusFilter('ADEQUATE')}
            className={`btn btn-sm ${statusFilter === 'ADEQUATE' ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              fontSize: '0.8rem',
              padding: '0.35rem 0.75rem',
              color: statusFilter === 'ADEQUATE' ? '#fff' : '#34d399',
            }}
          >
            Adequate Stock ({inventory.length - reorderCount})
          </button>
          <button
            onClick={() => setStatusFilter('EXPIRING')}
            className={`btn btn-sm ${statusFilter === 'EXPIRING' ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              fontSize: '0.8rem',
              padding: '0.35rem 0.75rem',
              color: statusFilter === 'EXPIRING' ? '#fff' : '#fbbf24',
              borderColor: statusFilter === 'EXPIRING' ? 'transparent' : 'rgba(245, 158, 11, 0.4)',
            }}
          >
            Expiring &le; 90d ({expiringSoonCount})
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card">
          <div className="loading-box">
            <div className="spinner" />
            <p>Loading inventory from database...</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              Stock Status ({filteredInventory.length} of {inventory.length} medicines)
            </h2>
            <span className="badge badge-blue">ERP Live Master Data</span>
          </div>
          <div className="table-container">
            <table className="data-table" id="inventory-table">
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th>Stock on Hand</th>
                  <th>Reorder Point</th>
                  <th>Daily Demand</th>
                  <th>Lead Time</th>
                  <th>Batch Expiry</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredInventory.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                      No medicine records matched your search / filter criteria.
                    </td>
                  </tr>
                ) : (
                  filteredInventory.map((item) => {
                    const isLowStock = item.current_stock <= item.reorder_point;
                    const daysLeft = getDaysUntilExpiry(item.expiry_date);
                    const isExpiringSoon = daysLeft <= 90;

                    return (
                      <tr key={item.med_id} id={`med-row-${item.med_id}`}>
                        <td>
                          <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>{item.name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                            ID: #{item.med_id}
                          </div>
                        </td>
                        <td>
                          <span
                            className="font-mono"
                            style={{
                              fontWeight: 700,
                              fontSize: '1.05rem',
                              color: isLowStock ? '#fb7185' : '#34d399',
                            }}
                          >
                            {item.current_stock}
                          </span>
                        </td>
                        <td className="font-mono">{item.reorder_point}</td>
                        <td className="font-mono">{item.daily_sales} / day</td>
                        <td>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={14} color="var(--text-muted)" />
                            {item.lead_time_days} days
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span className="font-mono" style={{ color: isExpiringSoon ? '#fbbf24' : 'var(--text-muted)' }}>
                              {item.expiry_date}
                            </span>
                            {isExpiringSoon && (
                              <span
                                className="badge badge-amber"
                                style={{ fontSize: '0.68rem', padding: '1px 5px' }}
                                title={`${daysLeft} days remaining`}
                              >
                                {daysLeft}d left
                              </span>
                            )}
                          </div>
                        </td>
                        <td>
                          {isLowStock ? (
                            <span className="badge badge-rose">
                              <AlertTriangle size={12} />
                              Reorder Needed
                            </span>
                          ) : (
                            <span className="badge badge-green">
                              <CheckCircle size={12} />
                              Adequate
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <div style={{ display: 'inline-flex', gap: '0.4rem', justifyContent: 'center' }}>
                            <button
                              id={`btn-batches-med-${item.med_id}`}
                              onClick={() => openBatchesModal(item)}
                              className="btn btn-sm btn-secondary"
                              title={`View lot batches for ${item.name}`}
                              style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem' }}
                            >
                              <Layers size={13} color="#38bdf8" />
                              <span>Batches</span>
                            </button>
                            <button
                              id={`btn-edit-med-${item.med_id}`}
                              onClick={() => openEditModal(item)}
                              className="btn btn-sm btn-edit"
                              title={`Edit ${item.name} master data`}
                              style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem' }}
                            >
                              <Edit3 size={13} />
                              <span>Edit</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Lot Batches Modal */}
      {viewingBatchesMed && (
        <div className="modal-backdrop" onClick={closeBatchesModal}>
          <div
            className="modal-dialog"
            style={{ maxWidth: '650px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="modal-title">
                <Layers size={18} color="#38bdf8" />
                <span>
                  Lot Batches: {viewingBatchesMed.name} (ID #{viewingBatchesMed.med_id})
                </span>
              </div>
              <button className="modal-close-btn" onClick={closeBatchesModal}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {loadingBatches ? (
                <div className="loading-box" style={{ padding: '2rem' }}>
                  <div className="spinner" />
                  <p>Loading batch lots from SQLite database...</p>
                </div>
              ) : batchesError ? (
                <div className="error-box">
                  <AlertTriangle size={16} />
                  <span>{batchesError}</span>
                </div>
              ) : batches.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
                  <Package size={32} color="var(--text-dim)" style={{ margin: '0 auto 0.75rem' }} />
                  <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                    No Segregated Lot Batches Recorded
                  </div>
                  <p style={{ fontSize: '0.85rem' }}>
                    Stock of {viewingBatchesMed.current_stock} units is currently tracked at the primary medicine level.
                    Receiving physical goods via Purchase Orders automatically records verified lot batches.
                  </p>
                </div>
              ) : (
                <div>
                  <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      Total Batch Records: <strong style={{ color: '#38bdf8' }}>{batches.length}</strong>
                    </div>
                    <span className="badge badge-blue">FIFO Lot Tracking</span>
                  </div>

                  <div className="table-container">
                    <table className="data-table" style={{ fontSize: '0.85rem' }}>
                      <thead>
                        <tr>
                          <th>Batch #</th>
                          <th>Lot Qty</th>
                          <th>Expiry Date</th>
                          <th>Received Date</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {batches.map((b) => {
                          const days = getDaysUntilExpiry(b.expiry_date);
                          const isExpired = days <= 0;
                          const isSoon = days > 0 && days <= 90;

                          return (
                            <tr key={b.batch_id || b.batch_number}>
                              <td className="font-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                                {b.batch_number}
                              </td>
                              <td className="font-mono" style={{ fontWeight: 700 }}>
                                {b.quantity}
                              </td>
                              <td className="font-mono">
                                <span style={{ color: isExpired ? '#fb7185' : isSoon ? '#fbbf24' : 'var(--text-main)' }}>
                                  {b.expiry_date}
                                </span>
                              </td>
                              <td className="font-mono" style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                                {b.received_at ? b.received_at.split('T')[0] : 'N/A'}
                              </td>
                              <td>
                                {isExpired ? (
                                  <span className="badge badge-rose" style={{ fontSize: '0.72rem' }}>
                                    Expired
                                  </span>
                                ) : isSoon ? (
                                  <span className="badge badge-amber" style={{ fontSize: '0.72rem' }}>
                                    {days}d Left
                                  </span>
                                ) : (
                                  <span className="badge badge-green" style={{ fontSize: '0.72rem' }}>
                                    Good ({days}d)
                                  </span>
                                )}
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

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={closeBatchesModal}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Master Data Modal */}
      {editingMed && (
        <div className="modal-backdrop" onClick={closeEditModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <Edit3 size={18} color="var(--accent-gold)" />
                <span>Edit Medicine: {editingMed.name}</span>
              </div>
              <button className="modal-close-btn" onClick={closeEditModal}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleEditSave}>
              <div className="modal-body">
                {editFormError && (
                  <div className="error-box" style={{ margin: 0, padding: '0.75rem 1rem' }}>
                    <AlertTriangle size={16} />
                    <span style={{ fontSize: '0.85rem' }}>{editFormError}</span>
                  </div>
                )}

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="input-current-stock">Current Stock</label>
                    <input
                      id="input-current-stock"
                      type="number"
                      name="current_stock"
                      className="form-input font-mono"
                      value={editFormData.current_stock}
                      onChange={handleEditInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Current physical units</span>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="input-reorder-point">Reorder Point</label>
                    <input
                      id="input-reorder-point"
                      type="number"
                      name="reorder_point"
                      className="form-input font-mono"
                      value={editFormData.reorder_point}
                      onChange={handleEditInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Threshold triggering replenishment</span>
                  </div>
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="input-daily-sales">Daily Sales (Demand)</label>
                    <input
                      id="input-daily-sales"
                      type="number"
                      name="daily_sales"
                      className="form-input font-mono"
                      value={editFormData.daily_sales}
                      onChange={handleEditInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Average units sold per day</span>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="input-lead-time">Lead Time (Days)</label>
                    <input
                      id="input-lead-time"
                      type="number"
                      name="lead_time_days"
                      className="form-input font-mono"
                      value={editFormData.lead_time_days}
                      onChange={handleEditInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Store restocking turnaround</span>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="input-expiry-date">Batch Expiry Date (YYYY-MM-DD)</label>
                  <input
                    id="input-expiry-date"
                    type="date"
                    name="expiry_date"
                    className="form-input font-mono"
                    value={editFormData.expiry_date}
                    onChange={handleEditInputChange}
                    required
                  />
                  <span className="form-help">Used for shelf-life capacity safety calculations</span>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={closeEditModal}
                  disabled={savingEdit}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={savingEdit}
                  id="btn-save-inventory"
                >
                  {savingEdit ? (
                    <>
                      <div className="spinner" style={{ width: 14, height: 14 }} />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Save size={14} />
                      <span>Save Master Data</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add New Medicine Modal */}
      {isAddOpen && (
        <div className="modal-backdrop" onClick={closeAddModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <Plus size={18} color="var(--accent-gold)" />
                <span>Add New Medicine to Inventory</span>
              </div>
              <button className="modal-close-btn" onClick={closeAddModal}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddSave}>
              <div className="modal-body">
                {addFormError && (
                  <div className="error-box" style={{ margin: 0, padding: '0.75rem 1rem' }}>
                    <AlertTriangle size={16} />
                    <span style={{ fontSize: '0.85rem' }}>{addFormError}</span>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label" htmlFor="add-medicine-name">Medicine Name</label>
                  <input
                    id="add-medicine-name"
                    type="text"
                    name="name"
                    className="form-input"
                    placeholder="e.g. Amoxicillin 500mg"
                    value={addFormData.name}
                    onChange={handleAddInputChange}
                    required
                    autoFocus
                  />
                  <span className="form-help">Must be a unique medicine name</span>
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="add-current-stock">Initial Stock</label>
                    <input
                      id="add-current-stock"
                      type="number"
                      name="current_stock"
                      className="form-input font-mono"
                      value={addFormData.current_stock}
                      onChange={handleAddInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Current shelf units</span>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="add-reorder-point">Reorder Point</label>
                    <input
                      id="add-reorder-point"
                      type="number"
                      name="reorder_point"
                      className="form-input font-mono"
                      value={addFormData.reorder_point}
                      onChange={handleAddInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Replenishment trigger</span>
                  </div>
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="add-daily-sales">Daily Sales (Demand)</label>
                    <input
                      id="add-daily-sales"
                      type="number"
                      name="daily_sales"
                      className="form-input font-mono"
                      value={addFormData.daily_sales}
                      onChange={handleAddInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Average daily consumption</span>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="add-lead-time">Lead Time (Days)</label>
                    <input
                      id="add-lead-time"
                      type="number"
                      name="lead_time_days"
                      className="form-input font-mono"
                      value={addFormData.lead_time_days}
                      onChange={handleAddInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Expected turnaround</span>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="add-expiry-date">Batch Expiry Date (YYYY-MM-DD)</label>
                  <input
                    id="add-expiry-date"
                    type="date"
                    name="expiry_date"
                    className="form-input font-mono"
                    value={addFormData.expiry_date}
                    onChange={handleAddInputChange}
                    required
                  />
                  <span className="form-help">Shelf life constraint for agent procurement safety</span>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={closeAddModal}
                  disabled={savingAdd}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={savingAdd}
                  id="btn-create-medicine"
                >
                  {savingAdd ? (
                    <>
                      <div className="spinner" style={{ width: 14, height: 14 }} />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Plus size={14} />
                      <span>Add to Inventory</span>
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
