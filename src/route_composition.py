"""Explicit opt-in zone policy; roles do not depend on selected visit modes."""
from collections import Counter

ROLES = ('anchor', 'supporting_stop', 'transition_stop')


def composition_assessment(stops, enabled):
    roles = [p.effective_primary_role for p in stops]
    counts = Counter(roles)
    longest, run = 0, 0
    for role in roles:
        run = run + 1 if role == 'transition_stop' else 0
        longest = max(longest, run)
    minimum = len(stops) >= 3
    passed = counts['anchor'] >= 1 and counts['anchor'] + counts['supporting_stop'] >= 2
    return dict(enabled=enabled, minimum_stop_count_passed=minimum,
        route_composition_passed=passed if enabled else None,
        primary_role_counts=dict(counts), longest_transition_run=longest,
        transition_soft_preference_passed=longest <= 2,
        basis='primary roles only; visit modes never promote roles',
        failure_reason=None if not enabled or passed else 'requires an anchor and at least two anchor/supporting stops')
