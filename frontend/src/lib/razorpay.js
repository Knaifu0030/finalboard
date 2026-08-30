let loading = null;

export function loadRazorpay() {
  if (window.Razorpay) return Promise.resolve(true);
  if (loading) return loading;
  loading = new Promise((resolve) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.async = true;
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
  return loading;
}

/* Opens the Razorpay modal. Resolves with the three fields the backend verifies,
   or {dismissed:true} / {failed:reason}. */
export async function openCheckout(order) {
  const ok = await loadRazorpay();
  if (!ok || !window.Razorpay) return { failed: "Checkout would not load." };
  return new Promise((resolve) => {
    let settled = false;
    const done = (v) => {
      if (!settled) {
        settled = true;
        resolve(v);
      }
    };
    const rzp = new window.Razorpay({
      key: order.key_id || process.env.REACT_APP_RAZORPAY_KEY_ID,
      order_id: order.order_id,
      amount: order.amount_paise,
      currency: order.currency || "INR",
      name: "The Last Billboard",
      description: `Paste over it for ${order.display_label}`,
      prefill: { name: order.name, email: order.email },
      notes: { reference: order.reference },
      theme: { color: "#141414", backdrop_color: "#F3E7D3" },
      handler: (res) =>
        done({
          razorpay_order_id: res.razorpay_order_id,
          razorpay_payment_id: res.razorpay_payment_id,
          razorpay_signature: res.razorpay_signature,
        }),
      modal: { ondismiss: () => done({ dismissed: true }), escape: true, backdropclose: false },
    });
    rzp.on("payment.failed", (e) =>
      done({ failed: e?.error?.description || "The payment did not go through." })
    );
    rzp.open();
  });
}
