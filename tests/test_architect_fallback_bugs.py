"""Bug-reproduction tests for architect_agent._services_from_communities.

Expected to FAIL against the current implementation.
"""

from types import SimpleNamespace

from agents.architect_agent import ArchitectAgent


def _agent():
    # __init__ needs a config; bypass it — we only exercise a pure method.
    return ArchitectAgent.__new__(ArchitectAgent)


def test_service_names_are_deterministic():
    """Same community assignment must yield the same service names every run.

    `modules = list(set(...))` makes name derivation order-dependent; the
    name must instead come from a stable (sorted) module ordering.
    """
    communities = {
        "user.login": 0, "user.logout": 0, "auth.hash": 0,
        "order.create": 1, "cart.add": 1,
    }
    stub = SimpleNamespace()
    names = {s.name for s in _agent()._services_from_communities(communities, stub)}
    assert names == {"auth-user-service", "cart-order-service"}, names


def test_service_names_are_unique():
    """Distinct communities that share their first two modules must still
    produce distinct service names (currently collide -> 'models-service' x N)."""
    communities = {
        "models.User": 0,
        "models.Order": 1,
        "models.Product": 2,
    }
    stub = SimpleNamespace()
    names = [s.name for s in _agent()._services_from_communities(communities, stub)]
    assert len(names) == len(set(names)), f"duplicate service names: {names}"
