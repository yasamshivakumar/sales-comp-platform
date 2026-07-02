import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import OrderForm from "./OrderForm";
import OrderUpload from "./OrderUpload";
import OrderList from "./OrderList";
import "./orders.css";

const TABS = [
  { id: "queue", label: "Order queue" },
  { id: "create", label: "Create order" },
  { id: "import", label: "Import CSV" },
];

function Orders() {
  const { info } = useToast();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState("queue");
  const [listRefreshKey, setListRefreshKey] = useState(0);

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab && TABS.some((t) => t.id === tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  const handleUploadSuccess = () => {
    setListRefreshKey((key) => key + 1);
    setActiveTab("queue");
    info("Orders imported. Open Order queue to mark Booked orders as Success.");
  };

  const handleOrderCreated = () => {
    setListRefreshKey((key) => key + 1);
  };

  return (
    <div className="orders-page">
      <PageHeader badge="Transactions" title="Orders" />

      <div className="orders-toolbar">
        <div className="orders-tabs" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`orders-tab${activeTab === tab.id ? " orders-tab--active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="orders-workspace">
        {activeTab === "queue" && <OrderList refreshKey={listRefreshKey} />}
        {activeTab === "create" && <OrderForm onOrderCreated={handleOrderCreated} />}
        {activeTab === "import" && <OrderUpload onUploadSuccess={handleUploadSuccess} />}
      </div>
    </div>
  );
}

export default Orders;
