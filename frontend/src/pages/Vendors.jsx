import React, { useEffect, useState } from 'react';
import {
  Users,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Truck,
  Edit3,
  X,
  Save,
  DollarSign,
  Plus,
  UserPlus,
  PackagePlus,
  Search,
  Sliders,
  ShieldCheck,
  Award,
  Layers,
  Clock,
  Mail,
  CreditCard,
  CheckCircle2,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

const VENDOR_PROFILES = {
  'Vendor A': {
    tag: 'Lowest Price / High MOQ',
    color: 'badge-blue',
    desc: 'Bulk wholesale pharmaceutical manufacturer. Lowest unit rates with larger minimum batches.',
  },
  'Vendor B': {
    tag: 'Fast Delivery / Flexible MOQ',
    color: 'badge-green',
    desc: 'Hero fast-turnaround distributor. 2-day delivery SLA with flexible low MOQ thresholds.',
  },
  'Vendor C': {
    tag: 'Regional Balanced',
    color: 'badge-purple',
    desc: 'Regional distributor with balanced pricing, medium MOQ, and reliable 4-day delivery.',
  },
  'Vendor D': {
    tag: 'Generic Medicine Leader',
    color: 'badge-blue',
    desc: 'Cost-effective generic formulation provider with competitive 3-4 day delivery.',
  },
  'Vendor E': {
    tag: 'Hospital Supply Distributor',
    color: 'badge-green',
    desc: 'High-compliance hospital supplier with high reliability and flexible delivery terms.',
  },
  'Vendor F': {
    tag: 'Specialty Pharmaceutical',
    color: 'badge-amber',
    desc: 'Specialty medication provider with rapid 1-2 day emergency fulfillment.',
  },
};

export default function Vendors() {
  const [vendors, setVendors] = useState([]);
  const [offers, setOffers] = useState([]);
  const [medicines, setMedicines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Tab: 'offers', 'suppliers', 'comparison'
  const [activeTab, setActiveTab] = useState('offers');

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState('');
  const [vendorFilter, setVendorFilter] = useState('ALL');

  // Supplier Comparison Medicine Selection
  const [selectedMedId, setSelectedMedId] = useState(1);

  // Edit Offer Modal State
  const [editingOffer, setEditingOffer] = useState(null);
  const [editFormData, setEditFormData] = useState({
    base_price: 0,
    min_qty: 0,
    delivery_days: 0,
  });
  const [editFormError, setEditFormError] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

  // Edit Vendor Modal State
  const [editingVendor, setEditingVendor] = useState(null);
  const [vendorFormData, setVendorFormData] = useState({
    name: '',
    reliability: 0.95,
    contact_email: '',
    payment_terms: 'Net 30',
  });
  const [vendorFormError, setVendorFormError] = useState(null);
  const [savingVendorEdit, setSavingVendorEdit] = useState(false);

  // Add Vendor Modal State
  const [isAddVendorOpen, setIsAddVendorOpen] = useState(false);
  const [newVendorData, setNewVendorData] = useState({
    name: '',
    reliability: 0.95,
    contact_email: '',
    payment_terms: 'Net 30',
  });
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

  const handleEditSave = async (e) => {
    e.preventDefault();
    setEditFormError(null);

    const basePrice = parseFloat(editFormData.base_price);
    const minQty = parseInt(editFormData.min_qty, 10);
    const deliveryDays = parseInt(editFormData.delivery_days, 10);

    if (isNaN(basePrice) || basePrice <= 0) {
      setEditFormError('Base Price must be a positive number greater than 0.');
      return;
    }
    if (isNaN(minQty) || minQty <= 0) {
      setEditFormError('Minimum Order Quantity (MOQ) must be a positive integer.');
      return;
    }
    if (isNaN(deliveryDays) || deliveryDays < 0) {
      setEditFormError('Delivery Days must be a non-negative integer.');
      return;
    }

    setSavingEdit(true);
    try {
      const res = await fetch(`${API_BASE}/vendor-offers/${editingOffer.vendor_id}/${editingOffer.med_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_price: basePrice,
          min_qty: minQty,
          delivery_days: deliveryDays,
        }),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Failed to update vendor offer');

      setSuccessMsg(`Successfully updated contract offer for ${editingOffer.vendor_name} - ${editingOffer.med_name}.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      closeEditModal();
      await fetchVendorData();
    } catch (err) {
      setEditFormError(err.message);
    } finally {
      setSavingEdit(false);
    }
  };

  // --- Edit Vendor Handlers ---
  const openEditVendorModal = (vendor) => {
    setEditingVendor(vendor);
    setVendorFormData({
      name: vendor.name,
      reliability: vendor.reliability || 0.95,
      contact_email: vendor.contact_email || '',
      payment_terms: vendor.payment_terms || 'Net 30',
    });
    setVendorFormError(null);
  };

  const closeEditVendorModal = () => {
    setEditingVendor(null);
    setVendorFormError(null);
  };

  const handleVendorEditSave = async (e) => {
    e.preventDefault();
    setVendorFormError(null);

    const name = vendorFormData.name.trim();
    const rel = parseFloat(vendorFormData.reliability);

    if (!name) {
      setVendorFormError('Supplier name is required.');
      return;
    }
    if (isNaN(rel) || rel < 0 || rel > 1) {
      setVendorFormError('Reliability must be between 0.0 and 1.0 (e.g. 0.95 for 95%).');
      return;
    }

    setSavingVendorEdit(true);
    try {
      const res = await fetch(`${API_BASE}/vendors/${editingVendor.vendor_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          reliability: rel,
          contact_email: vendorFormData.contact_email,
          payment_terms: vendorFormData.payment_terms,
        }),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Failed to update supplier record');

      setSuccessMsg(`Successfully updated supplier "${name}".`);
      setTimeout(() => setSuccessMsg(null), 4000);
      closeEditVendorModal();
      await fetchVendorData();
    } catch (err) {
      setVendorFormError(err.message);
    } finally {
      setSavingVendorEdit(false);
    }
  };

  // --- Add Vendor Handlers ---
  const openAddVendorModal = () => {
    setNewVendorData({
      name: '',
      reliability: 0.95,
      contact_email: '',
      payment_terms: 'Net 30',
    });
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

    const name = newVendorData.name.trim();
    const rel = parseFloat(newVendorData.reliability);

    if (!name) {
      setAddVendorError('Vendor name is required.');
      return;
    }

    setSavingVendor(true);
    try {
      const res = await fetch(`${API_BASE}/vendors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          reliability: isNaN(rel) ? 0.95 : rel,
          contact_email: newVendorData.contact_email,
          payment_terms: newVendorData.payment_terms,
        }),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Failed to create new vendor');

      setSuccessMsg(`Successfully added vendor "${name}" (ID: #${result.vendor?.vendor_id}).`);
      setTimeout(() => setSuccessMsg(null), 4000);
      closeAddVendorModal();
      await fetchVendorData();
    } catch (err) {
      setAddVendorError(err.message);
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

  const handleAddOfferSave = async (e) => {
    e.preventDefault();
    setAddOfferError(null);

    const vId = parseInt(newOfferData.vendor_id, 10);
    const mId = parseInt(newOfferData.med_id, 10);
    const price = parseFloat(newOfferData.base_price);
    const moq = parseInt(newOfferData.min_qty, 10);
    const delivery = parseInt(newOfferData.delivery_days, 10);

    if (isNaN(vId) || !vId) {
      setAddOfferError('Please select a supplier.');
      return;
    }
    if (isNaN(mId) || !mId) {
      setAddOfferError('Please select a medicine.');
      return;
    }
    if (isNaN(price) || price <= 0) {
      setAddOfferError('Price must be greater than 0.');
      return;
    }
    if (isNaN(moq) || moq <= 0) {
      setAddOfferError('MOQ must be greater than 0.');
      return;
    }
    if (isNaN(delivery) || delivery <= 0) {
      setAddOfferError('Delivery days must be greater than 0.');
      return;
    }

    setSavingOffer(true);
    try {
      const res = await fetch(`${API_BASE}/vendor-offers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vendor_id: vId,
          med_id: mId,
          base_price: price,
          min_qty: moq,
          delivery_days: delivery,
        }),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Failed to create offer');

      setSuccessMsg('Successfully registered new contract offer!');
      setTimeout(() => setSuccessMsg(null), 4000);
      closeAddOfferModal();
      await fetchVendorData();
    } catch (err) {
      setAddOfferError(err.message);
    } finally {
      setSavingOffer(false);
    }
  };

  // Filtered Offers
  const filteredOffers = offers.filter((o) => {
    const matchesSearch =
      (o.med_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (o.vendor_name || '').toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;
    if (vendorFilter === 'ALL') return true;
    return String(o.vendor_id) === String(vendorFilter);
  });

  // Comparison Offers for selected medicine
  const comparisonOffers = offers.filter((o) => o.med_id === Number(selectedMedId));
  const minPrice = comparisonOffers.length > 0 ? Math.min(...comparisonOffers.map((o) => o.base_price)) : 0;
  const minDelivery = comparisonOffers.length > 0 ? Math.min(...comparisonOffers.map((o) => o.delivery_days)) : 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Users size={28} color="#c084fc" />
            Supplier Network & Catalogs
          </h1>
          <p className="page-subtitle">
            Supplier SLAs &middot; Reliability Scores &middot; Contract Pricing &middot; Multi-Vendor Quotation Benchmarking
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button onClick={openAddVendorModal} className="btn btn-primary">
            <UserPlus size={16} />
            <span>Add Supplier</span>
          </button>
          <button onClick={openAddOfferModal} className="btn btn-secondary">
            <PackagePlus size={16} />
            <span>Add Offer</span>
          </button>
          <button onClick={fetchVendorData} className="btn btn-secondary" disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spinner' : ''} />
            <span>Refresh</span>
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
          <span>{error}</span>
        </div>
      )}

      {/* Notice Banner */}
      <div
        style={{
          background: 'rgba(56, 189, 248, 0.08)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: 'var(--radius-md)',
          padding: '0.75rem 1rem',
          marginBottom: '1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.85rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8' }}>
          <ShieldCheck size={18} />
          <span>
            <strong>Simulated Supplier Gateway:</strong> All quotation negotiations, response profiles, and counter-offers are executed locally in deterministic simulation demo mode.
          </span>
        </div>
        <span className="badge badge-blue">Demo Gateway Active</span>
      </div>

      {/* Sub Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setActiveTab('offers')}
          className={`btn ${activeTab === 'offers' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.5rem 1rem', fontSize: '0.88rem' }}
        >
          <span>Contract Catalog Offers ({offers.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('suppliers')}
          className={`btn ${activeTab === 'suppliers' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.5rem 1rem', fontSize: '0.88rem' }}
        >
          <span>Registered Suppliers ({vendors.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('comparison')}
          className={`btn ${activeTab === 'comparison' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ padding: '0.5rem 1rem', fontSize: '0.88rem' }}
        >
          <Award size={16} />
          <span>Multi-Supplier Comparison Matrix</span>
        </button>
      </div>

      {/* TAB 1: CONTRACT OFFERS */}
      {activeTab === 'offers' && (
        <div className="card">
          <div className="card-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
            <h2 className="card-title">Catalog Price & SLA Agreements ({filteredOffers.length} offers)</h2>

            {/* Search & Filter */}
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <div style={{ position: 'relative', minWidth: '200px' }}>
                <Search size={15} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Filter medicine or supplier..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="form-input"
                  style={{ paddingLeft: '32px', height: '36px', fontSize: '0.85rem' }}
                />
              </div>

              <select
                value={vendorFilter}
                onChange={(e) => setVendorFilter(e.target.value)}
                className="form-input"
                style={{ height: '36px', fontSize: '0.85rem', width: 'auto' }}
              >
                <option value="ALL">All Suppliers</option>
                {vendors.map((v) => (
                  <option key={v.vendor_id} value={v.vendor_id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th>Medicine</th>
                  <th>Contract Unit Price</th>
                  <th>MOQ Batch</th>
                  <th>Delivery SLA</th>
                  <th>Min Order Spend</th>
                  <th style={{ textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredOffers.map((o) => (
                  <tr key={`${o.vendor_id}-${o.med_id}`}>
                    <td>
                      <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>{o.vendor_name}</span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{o.med_name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        Med ID: #{o.med_id}
                      </div>
                    </td>
                    <td className="font-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                      ${Number(o.base_price).toFixed(2)}/u
                    </td>
                    <td className="font-mono">{o.min_qty} units</td>
                    <td>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={14} color="var(--text-muted)" />
                        {o.delivery_days} days
                      </span>
                    </td>
                    <td className="font-mono" style={{ color: '#34d399', fontWeight: 600 }}>
                      ${(Number(o.base_price) * Number(o.min_qty)).toFixed(2)}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button onClick={() => openEditModal(o)} className="btn btn-sm btn-edit">
                        <Edit3 size={13} />
                        <span>Edit Terms</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: REGISTERED SUPPLIERS */}
      {activeTab === 'suppliers' && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Registered Pharmaceutical Suppliers ({vendors.length})</h2>
            <span className="badge badge-purple">Reliability Scored</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem', padding: '1rem' }}>
            {vendors.map((v) => {
              const profile = VENDOR_PROFILES[v.name] || {
                tag: 'General Supplier',
                color: 'badge-blue',
                desc: 'Verified pharmaceutical distributor.',
              };
              const relPercent = Math.round((v.reliability || 0.95) * 100);

              return (
                <div
                  key={v.vendor_id}
                  style={{
                    background: 'var(--bg-subtle)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.25rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                      <div>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>{v.name}</h3>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                          Supplier ID: #{v.vendor_id}
                        </span>
                      </div>
                      <span className={`badge ${profile.color}`}>{profile.tag}</span>
                    </div>

                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                      {profile.desc}
                    </p>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.82rem', marginBottom: '1rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-dim)' }}>Reliability SLA:</span>
                        <span className="font-mono" style={{ fontWeight: 700, color: relPercent >= 95 ? '#34d399' : '#fbbf24' }}>
                          {relPercent}% on-time fulfillment
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-dim)' }}>Payment Terms:</span>
                        <span className="font-mono">{v.payment_terms || 'Net 30'}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-dim)' }}>Contact:</span>
                        <span style={{ color: '#38bdf8' }}>{v.contact_email || 'orders@pharma-nexus.local'}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <button onClick={() => openEditVendorModal(v)} className="btn btn-sm btn-secondary">
                      <Edit3 size={13} />
                      <span>Edit Supplier</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: MULTI-SUPPLIER COMPARISON MATRIX */}
      {activeTab === 'comparison' && (
        <div className="card">
          <div className="card-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h2 className="card-title">Supplier Benchmark & Trade-Off Matrix</h2>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Compare quotation proposals across suppliers for multi-factor decision reasoning
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>Evaluate Medicine:</span>
              <select
                value={selectedMedId}
                onChange={(e) => setSelectedMedId(Number(e.target.value))}
                className="form-input"
                style={{ height: '38px', minWidth: '180px', fontWeight: 600 }}
              >
                {medicines.map((m) => (
                  <option key={m.med_id} value={m.med_id}>
                    {m.name} (#{m.med_id})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ padding: '1rem' }}>
            {comparisonOffers.length === 0 ? (
              <div className="empty-box">
                <AlertTriangle className="empty-icon" />
                <p>No supplier offers found for the selected medicine.</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: `repeat(${comparisonOffers.length}, minmax(220px, 1fr))`, gap: '1rem', overflowX: 'auto' }}>
                {comparisonOffers.map((offer) => {
                  const isLowestPrice = offer.base_price === minPrice;
                  const isFastestDelivery = offer.delivery_days === minDelivery;
                  const vendorInfo = vendors.find((v) => v.vendor_id === offer.vendor_id) || {};
                  const rel = vendorInfo.reliability || 0.95;

                  return (
                    <div
                      key={offer.vendor_id}
                      style={{
                        background: 'var(--bg-subtle)',
                        border: isLowestPrice ? '2px solid #34d399' : isFastestDelivery ? '2px solid #38bdf8' : '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1.25rem',
                        position: 'relative',
                      }}
                    >
                      {isLowestPrice && (
                        <div style={{ position: 'absolute', top: '-10px', right: '12px', background: '#059669', color: '#fff', fontSize: '0.7rem', padding: '2px 8px', borderRadius: '10px', fontWeight: 700 }}>
                          BEST PRICE
                        </div>
                      )}
                      {isFastestDelivery && !isLowestPrice && (
                        <div style={{ position: 'absolute', top: '-10px', right: '12px', background: '#0284c7', color: '#fff', fontSize: '0.7rem', padding: '2px 8px', borderRadius: '10px', fontWeight: 700 }}>
                          FASTEST SLA
                        </div>
                      )}

                      <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.25rem' }}>{offer.vendor_name}</h3>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '1rem' }}>
                        SLA Reliability: {Math.round(rel * 100)}%
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        <div style={{ background: 'var(--bg-card)', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Base Quotation Rate</div>
                          <div className="font-mono" style={{ fontSize: '1.3rem', fontWeight: 800, color: isLowestPrice ? '#34d399' : '#38bdf8' }}>
                            ${Number(offer.base_price).toFixed(2)}/u
                          </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                          <span style={{ color: 'var(--text-dim)' }}>Minimum Order (MOQ):</span>
                          <span className="font-mono" style={{ fontWeight: 700 }}>{offer.min_qty} units</span>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                          <span style={{ color: 'var(--text-dim)' }}>Delivery Lead Time:</span>
                          <span className="font-mono" style={{ fontWeight: 700, color: isFastestDelivery ? '#38bdf8' : 'inherit' }}>
                            {offer.delivery_days} days
                          </span>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                          <span style={{ color: 'var(--text-dim)' }}>Min Order Value:</span>
                          <span className="font-mono" style={{ fontWeight: 800, color: '#34d399' }}>
                            ${(Number(offer.base_price) * Number(offer.min_qty)).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* EDIT OFFER MODAL */}
      {editingOffer && (
        <div className="modal-backdrop" onClick={closeEditModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Edit Contract Offer Terms</h3>
              <button onClick={closeEditModal} className="btn-close">&times;</button>
            </div>
            {editFormError && (
              <div className="error-box" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertTriangle size={18} />
                <span>{editFormError}</span>
              </div>
            )}
            <form onSubmit={handleEditSave} style={{ padding: '1.25rem 1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Base Unit Price ($)</label>
                <input
                  type="number"
                  step="0.01"
                  value={editFormData.base_price}
                  onChange={(e) => setEditFormData({ ...editFormData, base_price: e.target.value })}
                  className="form-input font-mono"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Minimum Order Quantity (MOQ)</label>
                <input
                  type="number"
                  value={editFormData.min_qty}
                  onChange={(e) => setEditFormData({ ...editFormData, min_qty: e.target.value })}
                  className="form-input font-mono"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Delivery SLA (Days)</label>
                <input
                  type="number"
                  value={editFormData.delivery_days}
                  onChange={(e) => setEditFormData({ ...editFormData, delivery_days: e.target.value })}
                  className="form-input font-mono"
                  required
                />
              </div>
              <div className="modal-footer" style={{ padding: '1rem 0 0', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" onClick={closeEditModal} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={savingEdit}>
                  {savingEdit ? 'Saving...' : 'Save Terms'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT VENDOR MODAL */}
      {editingVendor && (
        <div className="modal-backdrop" onClick={closeEditVendorModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Edit Supplier Profile</h3>
              <button onClick={closeEditVendorModal} className="btn-close">&times;</button>
            </div>
            {vendorFormError && (
              <div className="error-box" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertTriangle size={18} />
                <span>{vendorFormError}</span>
              </div>
            )}
            <form onSubmit={handleVendorEditSave} style={{ padding: '1.25rem 1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Supplier Name</label>
                <input
                  type="text"
                  value={vendorFormData.name}
                  onChange={(e) => setVendorFormData({ ...vendorFormData, name: e.target.value })}
                  className="form-input"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Reliability Score (0.0 to 1.0)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.0"
                  max="1.0"
                  value={vendorFormData.reliability}
                  onChange={(e) => setVendorFormData({ ...vendorFormData, reliability: e.target.value })}
                  className="form-input font-mono"
                  required
                />
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                  e.g. 0.98 represents a 98% on-time delivery record.
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Contact Email</label>
                <input
                  type="email"
                  value={vendorFormData.contact_email}
                  onChange={(e) => setVendorFormData({ ...vendorFormData, contact_email: e.target.value })}
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Payment Terms</label>
                <input
                  type="text"
                  value={vendorFormData.payment_terms}
                  onChange={(e) => setVendorFormData({ ...vendorFormData, payment_terms: e.target.value })}
                  className="form-input"
                  placeholder="e.g. Net 30"
                />
              </div>
              <div className="modal-footer" style={{ padding: '1rem 0 0', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" onClick={closeEditVendorModal} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={savingVendorEdit}>
                  {savingVendorEdit ? 'Saving...' : 'Save Supplier'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD VENDOR MODAL */}
      {isAddVendorOpen && (
        <div className="modal-backdrop" onClick={closeAddVendorModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Register New Supplier</h3>
              <button onClick={closeAddVendorModal} className="btn-close">&times;</button>
            </div>
            {addVendorError && (
              <div className="error-box" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertTriangle size={18} />
                <span>{addVendorError}</span>
              </div>
            )}
            <form onSubmit={handleAddVendorSave} style={{ padding: '1.25rem 1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Supplier Name *</label>
                <input
                  type="text"
                  value={newVendorData.name}
                  onChange={(e) => setNewVendorData({ ...newVendorData, name: e.target.value })}
                  placeholder="e.g. Apex BioPharma"
                  className="form-input"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Reliability Score (0.0 to 1.0)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.0"
                  max="1.0"
                  value={newVendorData.reliability}
                  onChange={(e) => setNewVendorData({ ...newVendorData, reliability: e.target.value })}
                  className="form-input font-mono"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Contact Email</label>
                <input
                  type="email"
                  value={newVendorData.contact_email}
                  onChange={(e) => setNewVendorData({ ...newVendorData, contact_email: e.target.value })}
                  placeholder="orders@apexpharma.com"
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Payment Terms</label>
                <input
                  type="text"
                  value={newVendorData.payment_terms}
                  onChange={(e) => setNewVendorData({ ...newVendorData, payment_terms: e.target.value })}
                  className="form-input"
                  placeholder="e.g. Net 30"
                />
              </div>
              <div className="modal-footer" style={{ padding: '1rem 0 0', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" onClick={closeAddVendorModal} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={savingVendor}>
                  {savingVendor ? 'Registering...' : 'Register Supplier'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD OFFER MODAL */}
      {isAddOfferOpen && (
        <div className="modal-backdrop" onClick={closeAddOfferModal}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Register Contract Offer</h3>
              <button onClick={closeAddOfferModal} className="btn-close">&times;</button>
            </div>
            {addOfferError && (
              <div className="error-box" style={{ margin: '1rem 1.5rem 0' }}>
                <AlertTriangle size={18} />
                <span>{addOfferError}</span>
              </div>
            )}
            <form onSubmit={handleAddOfferSave} style={{ padding: '1.25rem 1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Supplier *</label>
                <select
                  value={newOfferData.vendor_id}
                  onChange={(e) => setNewOfferData({ ...newOfferData, vendor_id: e.target.value })}
                  className="form-input"
                  required
                >
                  <option value="">Select Supplier...</option>
                  {vendors.map((v) => (
                    <option key={v.vendor_id} value={v.vendor_id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Medicine *</label>
                <select
                  value={newOfferData.med_id}
                  onChange={(e) => setNewOfferData({ ...newOfferData, med_id: e.target.value })}
                  className="form-input"
                  required
                >
                  <option value="">Select Medicine...</option>
                  {medicines.map((m) => (
                    <option key={m.med_id} value={m.med_id}>
                      {m.name} (#{m.med_id})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Base Unit Price ($) *</label>
                <input
                  type="number"
                  step="0.01"
                  value={newOfferData.base_price}
                  onChange={(e) => setNewOfferData({ ...newOfferData, base_price: e.target.value })}
                  className="form-input font-mono"
                  placeholder="e.g. 8.50"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Minimum Order Quantity (MOQ) *</label>
                <input
                  type="number"
                  value={newOfferData.min_qty}
                  onChange={(e) => setNewOfferData({ ...newOfferData, min_qty: e.target.value })}
                  className="form-input font-mono"
                  placeholder="e.g. 100"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Delivery SLA (Days) *</label>
                <input
                  type="number"
                  value={newOfferData.delivery_days}
                  onChange={(e) => setNewOfferData({ ...newOfferData, delivery_days: e.target.value })}
                  className="form-input font-mono"
                  placeholder="e.g. 2"
                  required
                />
              </div>
              <div className="modal-footer" style={{ padding: '1rem 0 0', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" onClick={closeAddOfferModal} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={savingOffer}>
                  {savingOffer ? 'Adding...' : 'Add Offer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
