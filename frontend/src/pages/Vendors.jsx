import React, { useEffect, useState } from 'react';
import { Users, RefreshCw, AlertTriangle, CheckCircle, Truck, Edit3, X, Save, DollarSign, Plus, UserPlus, PackagePlus } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

const VENDOR_PROFILES = {
  'Vendor A': {
    tag: 'Lowest Price / High MOQ',
    color: 'badge-blue',
    desc: 'Offers highest bulk discount with longer lead times. Best for planned large reorders.',
  },
  'Vendor B': {
    tag: 'Fast Delivery / Flexible MOQ',
    color: 'badge-green',
    desc: 'Fastest turnaround (2 days) with small batch sizes. Ideal for urgent stockout prevention.',
  },
  'Vendor C': {
    tag: 'Moderate / Balanced',
    color: 'badge-purple',
    desc: 'Balanced pricing and medium minimum order quantities with reliable 4-day delivery.',
  },
};

export default function Vendors() {
  const [vendors, setVendors] = useState([]);
  const [offers, setOffers] = useState([]);
  const [medicines, setMedicines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Edit Offer Modal State
  const [editingOffer, setEditingOffer] = useState(null);
  const [editFormData, setEditFormData] = useState({
    base_price: 0,
    min_qty: 0,
    delivery_days: 0,
  });
  const [editFormError, setEditFormError] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

  // Add Vendor Modal State
  const [isAddVendorOpen, setIsAddVendorOpen] = useState(false);
  const [newVendorName, setNewVendorName] = useState('');
  const [addVendorError, setAddVendorError] = useState(null);
  const [savingVendor, setSavingVendor] = useState(false);

  // Add Offer Modal State
  const [isAddOfferOpen, setIsAddOfferOpen] = useState(false);
  const [newOfferData, setNewOfferData] = useState({
    vendor_id: '',
    med_id: '',
    base_price: '',
    min_qty: '',
    delivery_days: '',
  });
  const [addOfferError, setAddOfferError] = useState(null);
  const [savingOffer, setSavingOffer] = useState(false);

  const fetchVendorData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [vendorsRes, offersRes, inventoryRes] = await Promise.all([
        fetch(`${API_BASE}/vendors`),
        fetch(`${API_BASE}/vendor-offers`),
        fetch(`${API_BASE}/inventory`),
      ]);

      if (!vendorsRes.ok || !offersRes.ok) {
        throw new Error('Failed to fetch vendor records or catalogs');
      }

      const vendorsData = await vendorsRes.json();
      const offersData = await offersRes.json();
      const inventoryData = inventoryRes.ok ? await inventoryRes.json() : [];

      setVendors(vendorsData);
      setOffers(offersData);
      setMedicines(inventoryData);
    } catch (err) {
      setError(err.message || 'Failed to connect to vendor endpoints');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVendorData();
  }, []);

  // --- Edit Offer Handlers ---
  const openEditModal = (offer) => {
    setEditingOffer(offer);
    setEditFormData({
      base_price: offer.base_price,
      min_qty: offer.min_qty,
      delivery_days: offer.delivery_days,
    });
    setEditFormError(null);
  };

  const closeEditModal = () => {
    setEditingOffer(null);
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

    const basePrice = parseFloat(editFormData.base_price);
    const minQty = parseInt(editFormData.min_qty, 10);
    const deliveryDays = parseInt(editFormData.delivery_days, 10);

    if (isNaN(basePrice) || basePrice <= 0) {
      setEditFormError('Base Price must be a positive number (> 0).');
      return;
    }
    if (isNaN(minQty) || minQty <= 0) {
      setEditFormError('Minimum Order Quantity (MOQ) must be a positive integer (> 0).');
      return;
    }
    if (isNaN(deliveryDays) || deliveryDays < 0) {
      setEditFormError('Delivery Days must be a non-negative integer (>= 0).');
      return;
    }

    setSavingEdit(true);
    try {
      const res = await fetch(`${API_BASE}/vendor-offers/${editingOffer.vendor_id}/${editingOffer.med_id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          base_price: basePrice,
          min_qty: minQty,
          delivery_days: deliveryDays,
        }),
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Failed to update vendor offer');
      }

      setSuccessMsg(
        `Successfully updated ${editingOffer.vendor_name} contract offer for ${editingOffer.med_name} in SQLite ERP.`
      );
      setTimeout(() => setSuccessMsg(null), 5000);
      closeEditModal();
      await fetchVendorData();
    } catch (err) {
      setEditFormError(err.message || 'Error saving vendor offer to backend.');
    } finally {
      setSavingEdit(false);
    }
  };

  // --- Add Vendor Handlers ---
  const openAddVendorModal = () => {
    setNewVendorName('');
    setAddVendorError(null);
    setIsAddVendorOpen(true);
  };

  const closeAddVendorModal = () => {
    setIsAddVendorOpen(false);
    setAddVendorError(null);
  };

  const handleAddVendorSave = async (e) => {
    e.preventDefault();
    setAddVendorError(null);

    const name = newVendorName.trim();
    if (!name) {
      setAddVendorError('Vendor name is required.');
      return;
    }

    setSavingVendor(true);
    try {
      const res = await fetch(`${API_BASE}/vendors`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name }),
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Failed to add vendor');
      }

      setSuccessMsg(`Successfully registered new vendor "${result.vendor?.name || name}" (ID: #${result.vendor?.vendor_id}) in SQLite ERP.`);
      setTimeout(() => setSuccessMsg(null), 5000);
      closeAddVendorModal();
      await fetchVendorData();
    } catch (err) {
      setAddVendorError(err.message || 'Error creating vendor.');
    } finally {
      setSavingVendor(false);
    }
  };

  // --- Add Offer Handlers ---
  const openAddOfferModal = () => {
    setNewOfferData({
      vendor_id: vendors.length > 0 ? vendors[0].vendor_id : '',
      med_id: medicines.length > 0 ? medicines[0].med_id : '',
      base_price: '',
      min_qty: '',
      delivery_days: '',
    });
    setAddOfferError(null);
    setIsAddOfferOpen(true);
  };

  const closeAddOfferModal = () => {
    setIsAddOfferOpen(false);
    setAddOfferError(null);
  };

  const handleAddOfferChange = (e) => {
    const { name, value } = e.target;
    setNewOfferData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleAddOfferSave = async (e) => {
    e.preventDefault();
    setAddOfferError(null);

    const vendorId = parseInt(newOfferData.vendor_id, 10);
    const medId = parseInt(newOfferData.med_id, 10);
    const basePrice = parseFloat(newOfferData.base_price);
    const minQty = parseInt(newOfferData.min_qty, 10);
    const deliveryDays = parseInt(newOfferData.delivery_days, 10);

    if (isNaN(vendorId)) {
      setAddOfferError('Please select a valid vendor.');
      return;
    }
    if (isNaN(medId)) {
      setAddOfferError('Please select a valid medicine.');
      return;
    }
    if (isNaN(basePrice) || basePrice <= 0) {
      setAddOfferError('Base price must be a positive number (> 0).');
      return;
    }
    if (isNaN(minQty) || minQty <= 0) {
      setAddOfferError('Minimum Order Quantity (MOQ) must be greater than 0.');
      return;
    }
    if (isNaN(deliveryDays) || deliveryDays <= 0) {
      setAddOfferError('Delivery Days must be greater than 0.');
      return;
    }

    setSavingOffer(true);
    try {
      const res = await fetch(`${API_BASE}/vendor-offers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vendor_id: vendorId,
          med_id: medId,
          base_price: basePrice,
          min_qty: minQty,
          delivery_days: deliveryDays,
        }),
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Failed to add contract offer');
      }

      setSuccessMsg(`Successfully registered new contract offer for ${result.offer?.vendor_name} — ${result.offer?.med_name} in SQLite ERP.`);
      setTimeout(() => setSuccessMsg(null), 5000);
      closeAddOfferModal();
      await fetchVendorData();
    } catch (err) {
      setAddOfferError(err.message || 'Error creating contract offer.');
    } finally {
      setSavingOffer(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Users size={28} color="#06b6d4" />
            Vendor Directory & Offers
          </h1>
          <p className="page-subtitle">
            Registered pharmaceutical suppliers, contract pricing catalogs, and editable master terms
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            id="btn-add-vendor"
            onClick={openAddVendorModal}
            className="btn btn-secondary"
          >
            <UserPlus size={16} />
            <span>Add Vendor</span>
          </button>
          <button
            id="btn-add-offer"
            onClick={openAddOfferModal}
            className="btn btn-primary"
            disabled={vendors.length === 0 || medicines.length === 0}
          >
            <PackagePlus size={16} />
            <span>Add Offer</span>
          </button>
          <button
            id="btn-refresh-vendors"
            onClick={fetchVendorData}
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? 'spinner' : ''} />
            <span>Refresh</span>
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
          </div>
        </div>
      )}

      {loading ? (
        <div className="card">
          <div className="loading-box">
            <div className="spinner" />
            <p>Loading vendor directory and offers from database...</p>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Vendor Catalog Cards */}
          <div className="grid-cards">
            {vendors.map((vendor) => {
              const profile = VENDOR_PROFILES[vendor.name] || {
                tag: 'Registered Supplier',
                color: 'badge-blue',
                desc: 'Registered pharmaceutical supplier in ERP.',
              };
              const vendorOffers = offers.filter((o) => o.vendor_id === vendor.vendor_id);

              return (
                <div key={vendor.vendor_id} className="vendor-card" id={`vendor-card-${vendor.vendor_id}`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                    <div>
                      <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{vendor.name}</h3>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        ID: #{vendor.vendor_id}
                      </span>
                    </div>
                    <span className={`badge ${profile.color}`}>{profile.tag}</span>
                  </div>

                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
                    {profile.desc}
                  </p>

                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                      Offered Catalog ({vendorOffers.length} items)
                    </div>
                    {vendorOffers.length === 0 ? (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontStyle: 'italic', padding: '0.5rem 0' }}>
                        No contract offers registered yet.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {vendorOffers.map((offer) => (
                          <div
                            key={offer.med_id}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              background: 'var(--bg-subtle)',
                              padding: '0.5rem 0.75rem',
                              borderRadius: 'var(--radius-sm)',
                              fontSize: '0.85rem',
                            }}
                          >
                            <span style={{ fontWeight: 600 }}>{offer.med_name}</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                              <span style={{ color: '#38bdf8' }}>${offer.base_price.toFixed(2)}</span>
                              <span style={{ color: 'var(--text-muted)' }}>MOQ: {offer.min_qty}</span>
                              <span style={{ color: '#34d399' }}>{offer.delivery_days}d</span>
                              <button
                                onClick={() => openEditModal(offer)}
                                className="btn btn-sm btn-edit"
                                style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
                                title={`Edit ${offer.vendor_name} offer for ${offer.med_name}`}
                              >
                                <Edit3 size={11} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Detailed All Offers Table */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">All Contract Offers Matrix ({offers.length} offers)</h2>
              <span className="badge badge-purple">ERP Contract Rates</span>
            </div>
            <div className="table-container">
              <table className="data-table" id="vendor-offers-table">
                <thead>
                  <tr>
                    <th>Vendor</th>
                    <th>Medicine</th>
                    <th>Base Price</th>
                    <th>Minimum Order Qty (MOQ)</th>
                    <th>Delivery Speed</th>
                    <th style={{ textAlign: 'center' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {offers.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                        No contract offers registered. Click "+ Add Offer" above to create one.
                      </td>
                    </tr>
                  ) : (
                    offers.map((offer, idx) => (
                      <tr key={`${offer.vendor_id}-${offer.med_id}-${idx}`}>
                        <td style={{ fontWeight: 700 }}>{offer.vendor_name}</td>
                        <td>{offer.med_name}</td>
                        <td className="font-mono" style={{ color: '#38bdf8', fontWeight: 600 }}>
                          ${offer.base_price.toFixed(2)}
                        </td>
                        <td className="font-mono">{offer.min_qty} units</td>
                        <td>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <Truck size={14} color="var(--text-muted)" />
                            {offer.delivery_days} days
                          </span>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            id={`btn-edit-offer-${offer.vendor_id}-${offer.med_id}`}
                            onClick={() => openEditModal(offer)}
                            className="btn btn-sm btn-edit"
                            title={`Edit ${offer.vendor_name} offer for ${offer.med_name}`}
                          >
                            <Edit3 size={13} />
                            <span>Edit Offer</span>
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Edit Vendor Offer Modal */}
      {editingOffer && (
        <div className="modal-backdrop" onClick={closeEditModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <DollarSign size={18} color="var(--accent-gold)" />
                <span>Edit Offer: {editingOffer.vendor_name} — {editingOffer.med_name}</span>
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

                <div className="form-group">
                  <label className="form-label" htmlFor="input-base-price">Base Wholesale Price ($ per unit)</label>
                  <input
                    id="input-base-price"
                    type="number"
                    step="0.01"
                    name="base_price"
                    className="form-input font-mono"
                    value={editFormData.base_price}
                    onChange={handleEditInputChange}
                    min="0.01"
                    required
                  />
                  <span className="form-help">Starting catalog rate before agent negotiation</span>
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="input-min-qty">Minimum Order Qty (MOQ)</label>
                    <input
                      id="input-min-qty"
                      type="number"
                      name="min_qty"
                      className="form-input font-mono"
                      value={editFormData.min_qty}
                      onChange={handleEditInputChange}
                      min="1"
                      required
                    />
                    <span className="form-help">Minimum lot size required</span>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="input-delivery-days">Delivery SLA (Days)</label>
                    <input
                      id="input-delivery-days"
                      type="number"
                      name="delivery_days"
                      className="form-input font-mono"
                      value={editFormData.delivery_days}
                      onChange={handleEditInputChange}
                      min="0"
                      required
                    />
                    <span className="form-help">Supplier fulfillment speed</span>
                  </div>
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
                  id="btn-save-offer"
                >
                  {savingEdit ? (
                    <>
                      <div className="spinner" style={{ width: 14, height: 14 }} />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Save size={14} />
                      <span>Save Contract Offer</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Vendor Modal */}
      {isAddVendorOpen && (
        <div className="modal-backdrop" onClick={closeAddVendorModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <UserPlus size={18} color="var(--accent-gold)" />
                <span>Register New Vendor</span>
              </div>
              <button className="modal-close-btn" onClick={closeAddVendorModal}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddVendorSave}>
              <div className="modal-body">
                {addVendorError && (
                  <div className="error-box" style={{ margin: 0, padding: '0.75rem 1rem' }}>
                    <AlertTriangle size={16} />
                    <span style={{ fontSize: '0.85rem' }}>{addVendorError}</span>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label" htmlFor="input-vendor-name">Vendor Name</label>
                  <input
                    id="input-vendor-name"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Apex Pharma Supply Ltd"
                    value={newVendorName}
                    onChange={(e) => setNewVendorName(e.target.value)}
                    required
                    autoFocus
                  />
                  <span className="form-help">Must be a unique registered vendor name</span>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={closeAddVendorModal}
                  disabled={savingVendor}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={savingVendor}
                  id="btn-create-vendor"
                >
                  {savingVendor ? (
                    <>
                      <div className="spinner" style={{ width: 14, height: 14 }} />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <UserPlus size={14} />
                      <span>Add Vendor</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Contract Offer Modal */}
      {isAddOfferOpen && (
        <div className="modal-backdrop" onClick={closeAddOfferModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <PackagePlus size={18} color="var(--accent-gold)" />
                <span>Register Contract Offer</span>
              </div>
              <button className="modal-close-btn" onClick={closeAddOfferModal}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddOfferSave}>
              <div className="modal-body">
                {addOfferError && (
                  <div className="error-box" style={{ margin: 0, padding: '0.75rem 1rem' }}>
                    <AlertTriangle size={16} />
                    <span style={{ fontSize: '0.85rem' }}>{addOfferError}</span>
                  </div>
                )}

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="select-vendor">Select Vendor</label>
                    <select
                      id="select-vendor"
                      name="vendor_id"
                      className="form-input"
                      value={newOfferData.vendor_id}
                      onChange={handleAddOfferChange}
                      required
                    >
                      {vendors.map((v) => (
                        <option key={v.vendor_id} value={v.vendor_id}>
                          {v.name} (ID: #{v.vendor_id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="select-medicine">Select Medicine</label>
                    <select
                      id="select-medicine"
                      name="med_id"
                      className="form-input"
                      value={newOfferData.med_id}
                      onChange={handleAddOfferChange}
                      required
                    >
                      {medicines.map((m) => (
                        <option key={m.med_id} value={m.med_id}>
                          {m.name} (ID: #{m.med_id})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-offer-base-price">Base Wholesale Price ($ per unit)</label>
                  <input
                    id="new-offer-base-price"
                    type="number"
                    step="0.01"
                    name="base_price"
                    className="form-input font-mono"
                    placeholder="e.g. 12.50"
                    value={newOfferData.base_price}
                    onChange={handleAddOfferChange}
                    min="0.01"
                    required
                  />
                  <span className="form-help">Starting catalogue rate</span>
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="new-offer-min-qty">Minimum Order Qty (MOQ)</label>
                    <input
                      id="new-offer-min-qty"
                      type="number"
                      name="min_qty"
                      className="form-input font-mono"
                      placeholder="e.g. 50"
                      value={newOfferData.min_qty}
                      onChange={handleAddOfferChange}
                      min="1"
                      required
                    />
                    <span className="form-help">Minimum batch size</span>
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="new-offer-delivery-days">Delivery SLA (Days)</label>
                    <input
                      id="new-offer-delivery-days"
                      type="number"
                      name="delivery_days"
                      className="form-input font-mono"
                      placeholder="e.g. 3"
                      value={newOfferData.delivery_days}
                      onChange={handleAddOfferChange}
                      min="1"
                      required
                    />
                    <span className="form-help">Delivery lead time</span>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={closeAddOfferModal}
                  disabled={savingOffer}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={savingOffer}
                  id="btn-create-offer"
                >
                  {savingOffer ? (
                    <>
                      <div className="spinner" style={{ width: 14, height: 14 }} />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Plus size={14} />
                      <span>Register Offer</span>
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
