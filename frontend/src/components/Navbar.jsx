import React, { useEffect, useState } from 'react';
import { Package, Users, Bot, MessageSquare, ShoppingCart, Activity, RefreshCw } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function Navbar({ activeTab, setActiveTab }) {
  const [backendStatus, setBackendStatus] = useState('checking');

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        setBackendStatus('online');
      } else {
        setBackendStatus('offline');
      }
    } catch {
      setBackendStatus('offline');
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: 'inventory', label: 'Inventory', icon: Package },
    { id: 'vendors', label: 'Vendors', icon: Users },
    { id: 'agent', label: 'Agent Control', icon: Bot },
    { id: 'negotiation', label: 'Negotiation', icon: MessageSquare },
    { id: 'purchase-orders', label: 'Purchase Orders', icon: ShoppingCart },
  ];

  return (
    <nav className="sidebar">
      <div className="brand-group">
        <div className="brand-icon">
          <Activity size={19} />
        </div>
        <div className="brand-text">
          <span className="brand-title">Pharma ERP</span>
          <span className="brand-tag">Phase 1</span>
        </div>
      </div>

      <ul className="nav-links">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <li key={item.id}>
              <button
                id={`nav-${item.id}`}
                onClick={() => setActiveTab(item.id)}
                className={`nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="sidebar-status">
        <span
          className={`status-dot ${backendStatus === 'online' ? 'green' : backendStatus === 'checking' ? 'amber' : 'rose'}`}
          title={`Backend API: ${backendStatus}`}
        />
        <span className="sidebar-status-text">
          {backendStatus === 'online' ? 'API Connected' : backendStatus === 'checking' ? 'Checking…' : 'API Disconnected'}
        </span>
        <button onClick={checkHealth} title="Refresh Connection" className="sidebar-refresh">
          <RefreshCw size={13} />
        </button>
      </div>
    </nav>
  );
}
