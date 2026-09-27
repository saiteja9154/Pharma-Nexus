import React, { useEffect, useState } from 'react';
import { Package, RefreshCw, AlertTriangle, CheckCircle, Clock, Edit3, X, Save, Plus } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function Inventory() {
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

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

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Package size={28} color="#38bdf8" />
            Inventory Management
          </h1>
          <p className="page-subtitle">
            Live stock levels, reorder thresholds, and lead times queried from SQLite ERP
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
            <h2 className="card-title">Stock Status ({inventory.length} medicines)</h2>
            <span className="badge badge-blue">ERP Live Data</span>
          </div>
          <div className="table-container">
            <table className="data-table" id="inventory-table">
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th>Stock</th>
                  <th>Reorder Point</th>
                  <th>Daily Sales</th>
                  <th>Lead Time</th>
                  <th>Expiry</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {inventory.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                      No inventory records found in database.
                    </td>
                  </tr>
                ) : (
                  inventory.map((item) => {
                    const isLowStock = item.current_stock <= item.reorder_point;
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
                        <td className="font-mono" style={{ color: 'var(--text-muted)' }}>
                          {item.expiry_date}
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
                          <button
                            id={`btn-edit-med-${item.med_id}`}
                            onClick={() => openEditModal(item)}
                            className="btn btn-sm btn-edit"
                            title={`Edit ${item.name} master data`}
                          >
                            <Edit3 size={13} />
                            <span>Edit</span>
                          </button>
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
