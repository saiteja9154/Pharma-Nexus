import React, { useState } from 'react';
import { Activity } from 'lucide-react';
import Navbar from './components/Navbar';
import Inventory from './pages/Inventory';
import Vendors from './pages/Vendors';
import AgentControl from './pages/AgentControl';
import Negotiation from './pages/Negotiation';
import PurchaseOrders from './pages/PurchaseOrders';

export default function App() {
  const [activeTab, setActiveTab] = useState('inventory');

  const renderContent = () => {
    switch (activeTab) {
      case 'inventory':
        return <Inventory />;
      case 'vendors':
        return <Vendors />;
      case 'agent':
        return <AgentControl />;
      case 'negotiation':
        return <Negotiation />;
      case 'purchase-orders':
        return <PurchaseOrders />;
      default:
        return <Inventory />;
    }
  };

  return (
    <div className="app-container">
      <div className="app-shell">
        <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
        <div className="content-column">
          <main className="main-content">
            <div key={activeTab} className="page-transition">
              {renderContent()}
            </div>
          </main>
          <footer className="app-footer">
            <Activity size={13} />
            <span>Pharma Nexus V2 &middot; Pharma ERP Smart Vendor Restocking &amp; Bargaining Agent</span>
          </footer>
        </div>
      </div>
    </div>
  );
}
