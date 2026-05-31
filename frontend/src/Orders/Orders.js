import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import OrderForm from "./OrderForm";
import OrderUpload from "./OrderUpload";

function Orders() {
  const { info } = useToast();

  const handleUploadSuccess = () => {
    info("Orders uploaded — commissions calculated. Check the Commissions page.");
  };

  return (
    <div>
      <PageHeader
        badge="Transactions"
        title="Orders"
        // subtitle="Create orders manually or bulk-upload a CSV to trigger commission calculations."
      />

      <div className="orders-grid">
        <OrderForm />
        <OrderUpload onUploadSuccess={handleUploadSuccess} />
      </div>
    </div>
  );
}

export default Orders;
