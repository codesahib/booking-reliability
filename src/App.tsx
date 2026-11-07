import { useCallback, useEffect, useRef, useState } from 'react'

type Mode = 'baseline' | 'improved'
type Reservation = { id: string; campsite_name: string; guest_label: string; arrival: string; departure: string; amount_cents: number; status: string }
type Delivery = { id: number; reservation_id: string; event_id: string; event_type: string; outcome: string; detail: string; created_at: string }
type Ledger = { id: number; reservation_id: string; event_id: string; kind: string; amount_cents: number }
type History = { id: number; reservation_id: string; event_id: string | null; status: string; detail: string }
type Incident = { id: number; reservation_id: string; event_id: string; delivery_id: number; severity: string; code: string; detail: string; resolved: number; created_at: string; resolved_at: string | null }
type ProviderEvent = { event_id: string; reservation_id: string; event_type: string; outcome: string }
type Event = { event_id: string; reservation_id: string; type: string; amount_cents: number }
type Fixture = { id: string; label: string; events: Event[] }
type Dashboard = {
  campsites: { id: string; name: string; nightly_cents: number }[];
  reservations: Reservation[]; deliveries: Delivery[]; ledger: Ledger[]; history: History[];
  incidents: Incident[]; provider_events: ProviderEvent[];
  metrics: { duplicate_ledger_entries: number; invariant_violations: number; duplicates_suppressed: number; open_alerts: number; deferred_events: number };
  violations: { reservation_id: string; code: string }[];
}
const money = (value: number) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(value / 100)
const errorDetail = (value: unknown): string => typeof value === 'string' ? value : Array.isArray(value)
  ? value.map(item => `${item.loc?.slice(1).join('.') || 'Input'}: ${item.msg}`).join('; ') : 'The local API could not complete this request.'

export default function App() {
  const [mode, setMode] = useState<Mode>('baseline')
  const [data, setData] = useState<Dashboard>()
  const [fixtures, setFixtures] = useState<Fixture[]>([])
  const [fixtureId, setFixtureId] = useState('duplicate-delivery')
  const [selected, setSelected] = useState('res-1001')
  const [incidentId, setIncidentId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [alertsOnly, setAlertsOnly] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const bookingAttempt = useRef({ payload: '', key: '' })
  const load = useCallback(async () => {
    const response = await fetch(`/api/${mode}/dashboard`)
    if (!response.ok) throw new Error('Could not load demo. Start the API on port 8003.')
    setData(await response.json())
  }, [mode])
  useEffect(() => {
    let active = true
    setData(undefined); setIncidentId(null); setMessage(''); setError(''); setSearch('')
    fetch(`/api/${mode}/dashboard`).then(async response => {
      if (!response.ok) throw new Error('Could not load demo. Start the API on port 8003.')
      const result: Dashboard = await response.json()
      if (active) { setData(result); setSelected('res-1001') }
    }).catch(e => { if (active) setError(String(e.message)) })
    return () => { active = false }
  }, [mode])
  useEffect(() => {
    fetch('/api/fixtures').then(async response => {
      if (!response.ok) throw new Error('Could not load replay fixtures.')
      setFixtures(await response.json())
    }).catch(e => setError(String(e.message)))
  }, [])
  const run = async (operation: () => Promise<void>) => {
    setBusy(true); setError(''); setMessage('')
    try { await operation() } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally {
      try { await load() } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
      setBusy(false)
    }
  }
  const postEvent = async (event: Event) => {
    const response = await fetch(`/api/${mode}/webhooks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event) })
    const result = await response.json()
    if (!response.ok && !result.outcome) throw new Error(errorDetail(result.detail))
    return { ...result, ok: response.ok }
  }
  const reservation = data?.reservations.find(r => r.id === selected)
  const send = (type: string) => run(async () => {
    if (!reservation) return
    const result = await postEvent({ event_id: `${selected}-${type}`, reservation_id: selected, type, amount_cents: reservation.amount_cents })
    if (!result.ok) throw new Error(`${result.event_id}: ${result.detail}`)
    setMessage(`${result.event_id}: ${result.detail}`)
  })
  const replay = () => run(async () => {
    const fixture = fixtures.find(item => item.id === fixtureId)
    if (!fixture || !reservation) return
    const outcomes: Record<string, number> = {}
    for (const event of fixture.events) {
      const result = await postEvent({ ...event, reservation_id: selected,
        event_id: selected === 'res-1001' ? event.event_id : `${selected}-${event.event_id}`,
        amount_cents: event.amount_cents === 4500 ? Math.floor(reservation.amount_cents / 2) : reservation.amount_cents })
      outcomes[result.outcome] = (outcomes[result.outcome] || 0) + 1
    }
    setMessage(`Replay complete: ${fixture.events.length} deliveries · ${Object.entries(outcomes).map(([key, count]) => `${count} ${key}`).join(' · ')}. Live results below.`)
  })
  const currentIncident = data?.incidents.find(item => item.id === incidentId)
  const incidentDelivery = data?.deliveries.find(item => item.id === currentIncident?.delivery_id)
  const matchingIncidents = data?.incidents.filter(item =>
    (!alertsOnly || (!item.resolved && item.severity !== 'info')) &&
    `${item.event_id} ${item.reservation_id} ${item.code}`.toLowerCase().includes(search.toLowerCase())) || []
  const shownDeliveries = data?.deliveries.filter(item => `${item.event_id} ${item.reservation_id}`.toLowerCase().includes(search.toLowerCase())) || []

  return <div className="app-shell">
    <header><a className="brand" href="/">◈ <span>fieldstation<span className="brand-sub">OPERATIONS LAB</span></span></a><span className="environment"><i /> Local sandbox · all payments simulated</span></header>
    <main>
      <div className="hero"><div><div className="eyebrow">ENGINEERING CASE STUDY / 03</div><h1>Every booking.<br/><em>Accounted for.</em></h1><p className="intro">Reproduce a payment incident. Trace its cause. Verify the fix.<br/>An independent, synthetic campground reliability lab.</p></div><div className="hero-note"><span className="eyebrow">THE RELIABILITY QUESTION</span><p>One payment.<br/>Three deliveries.<br/><strong>How many charges?</strong></p><span>Explore the same events before and after.</span></div></div>
      <div className="mode-tabs" role="group" aria-label="Workflow version"><button disabled={busy} aria-pressed={mode === 'baseline'} onClick={() => setMode('baseline')}>01 <span>Original workflow</span></button><button disabled={busy} aria-pressed={mode === 'improved'} onClick={() => setMode('improved')}>02 <span>Hardened workflow</span></button><span>Separate databases · identical seed</span></div>
      <section className={`workflow-bar ${mode}`}><div><strong>{mode === 'baseline' ? 'Delivery-driven accounting' : 'A durable identity for every event'}</strong><p>{mode === 'baseline' ? 'The legacy-like handler trusts each delivery. Repeated events can duplicate charges; support inspects logs manually.' : 'Retries are suppressed. Out-of-order refunds wait for their charge. Every decision keeps its investigation context.'}</p></div><span className={`pill ${mode === 'baseline' ? 'warning' : 'paid'}`}>{mode === 'baseline' ? 'Simulated weakness' : 'Transactional inbox'}</span></section>
      {error && <div role="alert" className="notice error">{error}</div>}
      {message && <div role="status" className="notice">{message}</div>}
      {!data ? <p>{error ? 'The API is unavailable. Check the run commands in README.md.' : 'Loading local reservations…'}</p> : <>
        <div className="metrics-caption">LIVE LAB CHECKS <span>Computed from the selected database · baseline checks are an evaluation overlay</span></div>
        <section className="metrics"><div><span>Webhook deliveries</span><strong data-testid="delivery-count">{data.deliveries.length}</strong><small>{data.reservations.length} reservations in this mode</small></div><div><span>Duplicate ledger entries</span><strong className={data.metrics.duplicate_ledger_entries ? 'bad-number' : ''} data-testid="duplicate-count">{data.metrics.duplicate_ledger_entries}</strong><small>{mode === 'improved' ? `${data.metrics.duplicates_suppressed} identical retries suppressed` : 'Repeated event identities in accounting'}</small></div><div><span>Invariant violations</span><strong className={data.metrics.invariant_violations ? 'bad-number' : ''} data-testid="violation-count">{data.metrics.invariant_violations}</strong><small>Current accounting + booking state</small></div><div><span>Open incident alerts</span><strong data-testid="alert-count">{mode === 'improved' ? data.metrics.open_alerts : '—'}</strong><small>{mode === 'improved' ? `${data.metrics.deferred_events} events awaiting a charge` : 'No incident classification in original'}</small></div></section>
        <section className="replay-bar"><div><span className="eyebrow">REPLAY A FAILURE FIXTURE</span><p>Uses the selected stay. Reset the demo for a clean comparison.</p></div><label className="sr-only" htmlFor="fixture">Replay scenario</label><select id="fixture" value={fixtureId} disabled={busy} onChange={e => setFixtureId(e.target.value)}>{fixtures.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select><button className="primary" disabled={busy || !fixtures.length} onClick={() => void replay()}>{busy ? 'Processing…' : 'Replay scenario'}</button></section>
        {!!data.violations.length && <div className="invariant-list" role="note"><strong>Evaluation found:</strong> {data.violations.map(item => `${item.reservation_id}: ${item.code}`).join(' · ')}</div>}
        <div className="workspace"><section className="panel"><div className="section-heading"><div><span className="eyebrow">01 / RESERVATION DESK</span><h2>Upcoming stays</h2></div><span className="pill">Synthetic seed</span></div>
          <div className="reservation-list">{data.reservations.map(r => <button key={r.id} disabled={busy} className={`reservation ${selected === r.id ? 'selected' : ''}`} aria-pressed={selected === r.id} onClick={() => setSelected(r.id)}><span className="site-icon" aria-hidden="true">♧</span><span><strong>{r.campsite_name}</strong><small>{r.id} · {r.arrival} → {r.departure}</small></span><span className={`pill ${r.status}`}>{r.status}</span></button>)}</div>
          <details className="booking-form"><summary>Create a synthetic booking</summary><form onSubmit={e => { e.preventDefault(); const form = new FormData(e.currentTarget); void run(async () => {
            const payload = { campsite_id: form.get('site'), guest_label: 'Demo walk-in', arrival: form.get('arrival'), departure: form.get('departure') }
            const serialized = JSON.stringify(payload)
            if (bookingAttempt.current.payload !== serialized) bookingAttempt.current = { payload: serialized, key: crypto.randomUUID() }
            const response = await fetch(`/api/${mode}/bookings`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...payload, idempotency_key: bookingAttempt.current.key }) })
            const result = await response.json(); if (!response.ok) throw new Error(errorDetail(result.detail))
            setSelected(result.id); setMessage(`Confirmed synthetic reservation ${result.id}; payment pending.`)
          }) }}><label>Campsite<select name="site">{data.campsites.map(s => <option value={s.id} key={s.id}>{s.name} · {money(s.nightly_cents)}/night</option>)}</select></label><div className="date-fields"><label>Arrival<input type="date" name="arrival" defaultValue="2027-07-01" required /></label><label>Departure<input type="date" name="departure" defaultValue="2027-07-03" required /></label></div><button disabled={busy} className="primary">Confirm booking</button></form></details>
        </section><section className="panel gateway"><span className="eyebrow">02 / FAKE PAYMENT GATEWAY</span><h2>Deliver an event</h2><p>Buttons reuse stable event IDs. Send payment success again to simulate an identical provider retry.</p><div className="booking-ref"><small>{selected}</small><strong>{reservation && money(reservation.amount_cents)}</strong><span>Fictional total · no funds move</span></div><div className="actions"><button disabled={busy} onClick={() => void send('authorized')}>Authorize</button><button disabled={busy} className="primary" onClick={() => void send('payment_succeeded')}>Send payment success</button><button disabled={busy} onClick={() => void send('refund_succeeded')}>Send refund success</button><button disabled={busy} onClick={() => void send('refund_failed')}>Send refund failure</button></div></section></div>
        <section className="panel incident-panel"><div className="section-heading"><div><span className="eyebrow">03 / INCIDENT INVESTIGATION</span><h2>{mode === 'improved' ? 'Every decision, in context' : 'Original investigation: inspect the log'}</h2></div>{mode === 'improved' && <label className="checkbox"><input type="checkbox" checked={alertsOnly} onChange={e => setAlertsOnly(e.target.checked)} />Open alerts only</label>}</div>
          {mode === 'baseline' ? <div className="manual-note"><span aria-hidden="true">⌕</span><div><strong>No correlated incident records in this workflow.</strong><p>Find an event ID in <code>data/logs/baseline.jsonl</code>, locate its reservation, compare the ledger, and check status against history. Switch to the hardened workflow to inspect a correlated record.</p></div></div> : <>
            <label className="search-label">Find reservation, event, or incident code<input type="search" placeholder="e.g. res-1001 or evt-payment" value={search} onChange={e => setSearch(e.target.value)} /></label>
            <div className="incident-list">{matchingIncidents.map(item => <button key={item.id} aria-pressed={incidentId === item.id} className={`incident-row ${incidentId === item.id ? 'active' : ''}`} onClick={() => { setIncidentId(item.id); if (data.reservations.some(r => r.id === item.reservation_id)) setSelected(item.reservation_id) }}><span className={`severity-dot ${item.severity}`} /><span><strong>{item.code.replaceAll('_', ' ')}</strong><small>{item.event_id} · {item.reservation_id} · delivery #{item.delivery_id}</small></span><span className={`pill ${item.resolved ? '' : 'warning'}`}>{item.resolved ? 'Recorded' : 'Open alert'}</span><span className="context-link">Inspect →</span></button>)}</div>
            {!matchingIncidents.length && <p className="empty">{data.incidents.length ? 'No incident records match this filter.' : 'No incident records yet. Replay duplicate delivery or send a refund failure after a charge.'}</p>}
            {currentIncident && <div className="incident-context" data-testid="incident-context"><div className="section-heading"><h3>{currentIncident.code}</h3><span className={`pill ${currentIncident.severity}`}>{currentIncident.severity}</span></div><p>{currentIncident.detail}</p><dl><div><dt>Reservation</dt><dd>{currentIncident.reservation_id}</dd></div><div><dt>Provider event</dt><dd>{currentIncident.event_id}</dd></div><div><dt>Delivery / result</dt><dd>#{currentIncident.delivery_id} · {incidentDelivery?.outcome}</dd></div><div><dt>Recorded (UTC)</dt><dd>{currentIncident.created_at}</dd></div></dl><p className="context-status">Current booking: <strong>{data.reservations.find(r => r.id === currentIncident.reservation_id)?.status || 'Unknown reservation'}</strong> · Ledger entries: <strong>{data.ledger.filter(row => row.reservation_id === currentIncident.reservation_id).length}</strong> · Inbox: <strong>{data.provider_events.find(row => row.event_id === currentIncident.event_id)?.outcome || 'Identity conflict'}</strong></p>{currentIncident.resolved_at && <small>Closed automatically at {currentIncident.resolved_at}; historical delivery result is retained.</small>}</div>}
          </>}
        </section>
        <section className="panel trail"><span className="eyebrow">04 / DELIVERY AUDIT</span><h2>Payment event trail</h2><div className="table-scroll"><table><thead><tr><th>Event / reservation</th><th>Type</th><th>Result</th><th>Context</th></tr></thead><tbody>{shownDeliveries.map(d => <tr key={d.id}><td><code>{d.event_id}</code><small>{d.reservation_id} · delivery #{d.id}</small></td><td>{d.event_type}</td><td><span className={`pill ${d.outcome}`}>{d.outcome}</span></td><td>{d.detail}</td></tr>)}</tbody></table>{!shownDeliveries.length && <p className="empty">{data.deliveries.length ? 'No deliveries match the search.' : 'No events yet. Select a stay and send a simulated payment.'}</p>}</div></section>
        <div className="workspace"><section className="panel" data-testid="ledger"><div className="section-heading"><h2>Reservation ledger</h2><span className="pill">{selected}</span></div>{data.ledger.filter(l => l.reservation_id === selected).map(l => <div className="history-row" key={l.id}><span><code>{l.event_id}</code><small>Entry #{l.id} · {l.kind}</small></span><strong>{money(l.amount_cents)}</strong></div>)}{!data.ledger.some(l => l.reservation_id === selected) && <p className="empty">No accounting entries for this stay.</p>}</section><section className="panel"><h2>Booking history</h2>{data.history.filter(h => h.reservation_id === selected).map(h => <div className="history-row" key={h.id}><span><strong>{h.status}</strong><small>{h.detail}</small>{h.event_id && <code>{h.event_id}</code>}</span></div>)}</section></div>
      </>}
      <footer>Independent synthetic demonstration · No real payments or customer data · Codex-assisted engineering, deterministic runtime</footer>
    </main>
  </div>
}
