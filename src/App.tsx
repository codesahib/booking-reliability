import { useEffect, useState } from 'react'

type Reservation = { id: string; campsite_name: string; guest_label: string; arrival: string; departure: string; amount_cents: number; status: string }
type Delivery = { id: number; reservation_id: string; event_id: string; event_type: string; outcome: string; detail: string }
type Ledger = { id: number; reservation_id: string; event_id: string; kind: string; amount_cents: number }
type History = { id: number; reservation_id: string; event_id: string | null; status: string; detail: string }
type Dashboard = { campsites: { id: string; name: string; nightly_cents: number }[]; reservations: Reservation[]; deliveries: Delivery[]; ledger: Ledger[]; history: History[] }
const money = (value: number) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(value / 100)

export default function App() {
  const [data, setData] = useState<Dashboard>()
  const [selected, setSelected] = useState('res-1001')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = async () => {
    const response = await fetch('/api/baseline/dashboard')
    if (!response.ok) throw new Error('Could not load demo. Start the API on port 8003.')
    setData(await response.json())
  }
  useEffect(() => { load().catch(e => setError(String(e.message))) }, [])
  const run = async (operation: () => Promise<void>) => {
    setBusy(true); setError(''); setMessage('')
    try { await operation(); await load() } catch (e) { setError(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const send = (type: string) => run(async () => {
    const reservation = data!.reservations.find(r => r.id === selected)!
    const event = { event_id: `${selected}-${type}`, reservation_id: selected, type, amount_cents: reservation.amount_cents }
    const response = await fetch('/api/baseline/webhooks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event) })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail)
    setMessage(`${result.event_id}: ${result.detail}`)
  })
  const reservation = data?.reservations.find(r => r.id === selected)
  return <div className="app-shell">
    <header><a className="brand" href="/">◈ <span>fieldstation<span className="brand-sub">OPERATIONS LAB</span></span></a><span className="environment"><i /> Local sandbox · all payments simulated</span></header>
    <main>
      <div className="eyebrow">ENGINEERING CASE STUDY / 03</div>
      <h1>Every booking.<br/><em>Accounted for.</em></h1>
      <p className="intro">A campground reservation desk and payment incident lab.<br/>Follow a booking from confirmation to its accounting trail.</p>
      <section className="workflow-bar"><div><strong>Original workflow</strong><p>Events apply on arrival. Support investigates JSON logs manually.</p></div><span className="pill warning">Baseline</span></section>
      {error && <div role="alert" className="notice error">{error}</div>}
      {message && <div role="status" className="notice">{message}</div>}
      {!data ? <p>Loading local reservations…</p> : <>
        <section className="metrics"><div><span>Reservations</span><strong>{data.reservations.length}</strong><small>Fictional campers</small></div><div><span>Webhook deliveries</span><strong>{data.deliveries.length}</strong><small>Received locally</small></div><div><span>Ledger entries</span><strong>{data.ledger.length}</strong><small>Simulated accounting</small></div></section>
        <div className="workspace"><section className="panel"><div className="section-heading"><div><span className="eyebrow">01 / RESERVATION DESK</span><h2>Upcoming stays</h2></div><span className="pill">June 2027 seed</span></div>
          <div className="reservation-list">{data.reservations.map(r => <button key={r.id} className={`reservation ${selected === r.id ? 'selected' : ''}`} onClick={() => setSelected(r.id)}><span className="site-icon">♧</span><span><strong>{r.campsite_name}</strong><small>{r.id} · {r.arrival} → {r.departure}</small></span><span className={`pill ${r.status}`}>{r.status}</span></button>)}</div>
          <details className="booking-form"><summary>Create a synthetic booking</summary><form onSubmit={e => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => {
            const payload = { campsite_id: form.get('site'), guest_label: 'Demo walk-in', arrival: form.get('arrival'), departure: form.get('departure'), idempotency_key: crypto.randomUUID() }
            const response = await fetch('/api/baseline/bookings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            const result = await response.json(); if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Check dates: stay must be 1–30 nights.')
            setSelected(result.id); setMessage(`Confirmed synthetic reservation ${result.id}; payment pending.`)
          }) }}><label>Campsite<select name="site">{data.campsites.map(s => <option value={s.id} key={s.id}>{s.name} · {money(s.nightly_cents)}/night</option>)}</select></label><div className="date-fields"><label>Arrival<input type="date" name="arrival" defaultValue="2027-07-01" required /></label><label>Departure<input type="date" name="departure" defaultValue="2027-07-03" required /></label></div><button disabled={busy} className="primary">Confirm booking</button></form></details>
        </section><section className="panel gateway"><span className="eyebrow">02 / FAKE PAYMENT GATEWAY</span><h2>Deliver an event</h2><p>Stable event IDs let you send an identical delivery again.</p><div className="booking-ref"><small>{selected}</small><strong>{reservation && money(reservation.amount_cents)}</strong><span>Fictional total · no funds move</span></div><div className="actions"><button disabled={busy} onClick={() => void send('authorized')}>Authorize</button><button disabled={busy} className="primary" onClick={() => void send('payment_succeeded')}>Send payment success</button><button disabled={busy} onClick={() => void send('refund_succeeded')}>Send refund success</button><button disabled={busy} onClick={() => void send('refund_failed')}>Send refund failure</button></div></section></div>
        <section className="panel trail"><span className="eyebrow">03 / ADMIN BOOKING HISTORY</span><h2>Payment event trail</h2><div className="table-scroll"><table><thead><tr><th>Event / reservation</th><th>Type</th><th>Result</th><th>Context</th></tr></thead><tbody>{data.deliveries.map(d => <tr key={d.id}><td><code>{d.event_id}</code><small>{d.reservation_id}</small></td><td>{d.event_type}</td><td><span className="pill">{d.outcome}</span></td><td>{d.detail}</td></tr>)}</tbody></table>{!data.deliveries.length && <p className="empty">No events yet. Select a stay and send a simulated payment.</p>}</div></section>
        <div className="workspace"><section className="panel"><h2>Ledger</h2>{data.ledger.map(l => <div className="history-row" key={l.id}><span><code>{l.event_id}</code><small>{l.reservation_id} · {l.kind}</small></span><strong>{money(l.amount_cents)}</strong></div>)}{!data.ledger.length && <p className="empty">No accounting entries.</p>}</section><section className="panel"><h2>Booking history</h2>{data.history.filter(h => h.reservation_id === selected).map(h => <div className="history-row" key={h.id}><span><strong>{h.status}</strong><small>{h.detail}</small></span></div>)}</section></div>
      </>}
      <footer>Independent synthetic demonstration · Inspired by campground SaaS workflows · No runtime AI</footer>
    </main>
  </div>
}
