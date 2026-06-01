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
      />

      <div className="orders-grid">
        <OrderForm />
        <OrderUpload onUploadSuccess={handleUploadSuccess} />
      </div>
    </div>
  );
}

export default Orders;
