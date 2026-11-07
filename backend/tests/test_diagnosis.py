import pytest

from backend.replay import fixtures, scenario_assertions


class KnownBaselineShortcoming(Exception):
    pass


EXPECTED_FAILURES = {
    'ordinary-payment': set(),
    'duplicate-delivery': {'charge_count', 'invariants'},
    'late-authorization': {'final_status', 'invariants'},
    'early-refund': {'final_status', 'invariants'},
    'failed-refund': {'alert_context'},
    'wrong-amount': {'final_status', 'charge_count', 'invariants', 'alert_context'},
    'event-id-conflict': {'final_status', 'refund_count', 'invariants', 'alert_context'},
}


@pytest.mark.parametrize('scenario', [
    pytest.param(scenario, id=scenario['id'], marks=(
        pytest.mark.xfail(strict=True, raises=KnownBaselineShortcoming,
                          reason='Documented baseline retry/order/diagnostic shortcoming')
        if scenario['id'] != 'ordinary-payment' else ()))
    for scenario in fixtures()
])
def test_baseline_against_reliability_targets(client, scenario):
    for event in scenario['events']:
        assert client.post('/api/baseline/webhooks', json=event).status_code == 200
    checks = scenario_assertions(scenario, client.get('/api/baseline/dashboard').json())
    failures = {name for name, passed in checks.items() if not passed}
    # Only the exact documented mismatch is expected; HTTP/storage errors or
    # changed failure signatures must fail normally instead of hiding in xfail.
    assert failures == EXPECTED_FAILURES[scenario['id']]
    if failures:
        raise KnownBaselineShortcoming(', '.join(sorted(failures)))
