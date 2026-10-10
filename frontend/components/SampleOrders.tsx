"use client";

import { ArrowUpRight, Package, Truck } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";
import type { Order } from "@/types/call";

export default function SampleOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    fetch(`${apiUrl}/orders`, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(); return response.json(); })
      .then(data => setOrders(data.orders))
      .catch(error => { if (error.name !== "AbortError") setError(true); });
    return () => controller.abort();
  }, [attempt]);

  return <section className="panel orders-panel" id="orders" aria-labelledby="orders-title">
    <div className="panel-heading"><h2 id="orders-title">Try a sample order</h2><Package size={20} /></div>
    <p className="section-note">Say an order ID to ask Aria about it.</p>
    {error && <p className="load-error">Couldn’t load orders. Start the backend, then <button onClick={() => setAttempt(value => value + 1)}>retry</button>.</p>}
    {!orders.length && !error && <p className="section-note">Loading sample records…</p>}
    <div className="order-list">{orders.map(order => <article className="order" key={order.order_id}>
      <div className="flex items-center justify-between gap-2"><h3>{order.order_id}</h3><span className={`order-status ${order.status === "Processing" ? "processing" : ""}`}>{order.status}</span></div>
      <p className="customer-name">{order.customer_name}</p>
      <p className="product-name">{order.products.join(" + ")} <span>₹{order.order_value.toLocaleString("en-IN")}</span></p>
      {order.courier && <p className="order-detail"><Truck size={14} />{order.courier}<span>{order.tracking_number}</span></p>}
      <p className="order-note">{order.delivery_note || order.order_note}</p>
      <p className="eligibility">{order.cancellation.eligible ? "Eligible for cancellation" : "Not eligible for cancellation"}</p>
    </article>)}</div>
    <div className="fixture-note"><ArrowUpRight size={15} /><p>These are assessment fixtures.<br />Delivery notes aren’t live courier updates.</p></div>
  </section>;
}

