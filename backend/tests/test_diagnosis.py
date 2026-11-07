import pytest

from backend.replay import fixtures, scenario_assertions


@pytest.mark.parametrize('scenario', [
    pytest.param(scenario, id=scenario['id'], marks=(
        pytest.mark.xfail(strict=True, reason='Documented baseline retry/order/diagnostic shortcoming')
        if scenario['id'] != 'ordinary-payment' else ()))
    for scenario in fixtures()
])
def test_baseline_against_reliability_targets(client, scenario):
    for event in scenario['events']:
        client.post('/api/baseline/webhooks', json=event)
    checks = scenario_assertions(scenario, client.get('/api/baseline/dashboard').json())
    assert all(checks.values()), checks
