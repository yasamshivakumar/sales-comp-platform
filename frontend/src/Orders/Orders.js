import { Navigate, Route, Routes, useSearchParams, Link } from "react-router-dom";
import { useEffect, useState } from "react";
import TransactionCenter from "./TransactionCenter";
import TransactionWorkspace from "./TransactionWorkspace";
import OrderForm from "./OrderForm";
import OrderUpload from "./OrderUpload";
import "./orders.css";

function CreatePage({ onCreated }) {
  return (
    <div className="tx-subpage">
      <Link className="cp-btn-ghost" to="/orders" style={{ alignSelf: "flex-start" }}>
        ← Orders
      </Link>
      <OrderForm onOrderCreated={onCreated} />
    </div>
  );
}

function ImportPage({ onDone }) {
  return (
    <div className="tx-subpage">
      <OrderUpload onUploadSuccess={onDone} />
    </div>
  );
}

/**
 * Sales Transaction Operations — routes
 * /orders           → Operations Center
 * /orders/new       → Create
 * /orders/import    → Import wizard
 * /orders/:id/*     → Detail workspace
 */
function Orders() {
  const [searchParams] = useSearchParams();
  const [refreshKey, setRefreshKey] = useState(0);

  // Legacy ?tab= support
  const legacyTab = searchParams.get("tab");

  useEffect(() => {
    // no-op; center reads refreshKey via remount keys when needed
  }, [legacyTab]);

  return (
    <Routes>
      <Route
        index
        element={
          legacyTab === "create" ? (
            <Navigate to="new" replace />
          ) : legacyTab === "import" ? (
            <Navigate to="import" replace />
          ) : (
            <TransactionCenter refreshKey={refreshKey} />
          )
        }
      />
      <Route
        path="new"
        element={<CreatePage onCreated={() => setRefreshKey((k) => k + 1)} />}
      />
      <Route
        path="import"
        element={<ImportPage onDone={() => setRefreshKey((k) => k + 1)} />}
      />
      <Route path=":orderId/*" element={<TransactionWorkspace />} />
      <Route path="*" element={<Navigate to="." replace />} />
    </Routes>
  );
}

export default Orders;
