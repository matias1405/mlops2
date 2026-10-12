from types import SimpleNamespace

import pytest

from movierec_ml.release import promote


class FakeClient:
    def __init__(self, versions: dict[str, dict], aliases: dict[str, str]):
        self.versions, self.aliases, self.tags = versions, dict(aliases), {}

    def _mv(self, v):
        return SimpleNamespace(version=v, tags=self.versions[v])

    def get_model_version(self, name, version):
        return self._mv(version)

    def get_model_version_by_alias(self, name, alias):
        if alias not in self.aliases:
            raise LookupError(alias)
        return self._mv(self.aliases[alias])

    def set_registered_model_alias(self, name, alias, version):
        self.aliases[alias] = version

    def set_model_version_tag(self, name, version, key, value):
        self.tags[(version, key)] = value


def deps(calls):
    return {
        "validate": lambda: calls.append("validate") or {"checks": {}},
        "sync": lambda env: calls.append(f"sync:{env}") or {"rows": 1},
        "reload": lambda env: calls.append(f"reload:{env}") or {"status": "reloaded"},
    }


@pytest.fixture
def client():
    ok = {"contract_version": "2"}
    return FakeClient({"1": ok, "2": ok, "3": {"contract_version": "99"}}, {"dev": "2", "production": "1"})


def test_promote_dev_valida_en_dev_y_asigna_production(client):
    calls = []
    out = promote("dev", client=client, **deps(calls))
    assert calls == ["validate", "sync:prod", "reload:prod"]
    assert client.aliases["production"] == "2" and out["production"] == "1 -> 2" and out["validated_in_dev"]
    assert ("2", "promoted_at") in client.tags


def test_rollback_a_una_version_sin_validar_en_dev(client):
    calls = []
    client.aliases["production"] = "2"
    out = promote("1", client=client, **deps(calls))
    assert calls == ["sync:prod", "reload:prod"] and not out["validated_in_dev"]
    assert client.aliases["production"] == "1"


def test_contrato_incompatible_no_toca_production(client):
    with pytest.raises(RuntimeError, match="contrato"):
        promote("3", client=client, **deps([]))
    assert client.aliases["production"] == "1"


def test_version_invalida(client):
    with pytest.raises(ValueError):
        promote("ultima", client=client, **deps([]))


def test_recommender_caido_falla(client):
    d = deps([])
    d["reload"] = lambda env: {"status": "unreachable"}
    with pytest.raises(RuntimeError, match="no responde"):
        promote("1", client=client, **d)
