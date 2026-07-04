import { useState } from "react";
import api from "../api";

export function useBookDemo() {
  const [demoForm, setDemoForm] = useState({
    name: "",
    email: "",
    company: "",
    phone: "",
    message: "",
  });
  const [demoStatus, setDemoStatus] = useState({ type: "", message: "" });
  const [demoSubmitting, setDemoSubmitting] = useState(false);

  const updateDemoForm = (field) => (event) => {
    setDemoForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const submitDemoRequest = async (event) => {
    event.preventDefault();
    setDemoStatus({ type: "", message: "" });
    setDemoSubmitting(true);
    try {
      await api.post("marketing/book-demo/", demoForm);
      setDemoStatus({
        type: "success",
        message: "Request received. Our team will contact you within one business day.",
      });
      setDemoForm({ name: "", email: "", company: "", phone: "", message: "" });
    } catch (err) {
      const fallbackEmail = err.response?.data?.contact_email || "shivakumar@incentra.co.in";
      const fallbackPhone = err.response?.data?.contact_phone || "8499087617";
      setDemoStatus({
        type: "error",
        message:
          err.response?.data?.error ||
          `Unable to submit online. Email ${fallbackEmail} or call ${fallbackPhone}.`,
        email: fallbackEmail,
        phone: fallbackPhone,
      });
    } finally {
      setDemoSubmitting(false);
    }
  };

  return {
    demoForm,
    demoStatus,
    demoSubmitting,
    updateDemoForm,
    submitDemoRequest,
  };
}
