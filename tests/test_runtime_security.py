from types import SimpleNamespace

from backend.core.runtime_security import (
    CLOUDFLARE_IP_RANGES,
    extract_calculate_api_key,
    load_trusted_proxy_networks,
    parse_calculate_api_key_identities,
)


def test_load_trusted_proxy_networks_accepts_ip_and_cidr_tokens():
    networks = load_trusted_proxy_networks("127.0.0.1, 10.0.0.0/8")
    assert str(networks[0]) == "127.0.0.1/32"
    assert str(networks[1]) == "10.0.0.0/8"


def test_load_trusted_proxy_networks_ignores_invalid_tokens():
    networks = load_trusted_proxy_networks("not-a-network,1.2.3.4")
    assert [str(network) for network in networks] == ["1.2.3.4/32"]


def test_parse_calculate_api_key_identities_hashes_keys():
    identities = parse_calculate_api_key_identities("alpha beta")
    assert sorted(identities.keys()) == ["alpha", "beta"]
    assert identities["alpha"].startswith("api_key:")
    assert len(identities["alpha"]) == len("api_key:") + 12


def test_extract_calculate_api_key_prefers_explicit_header():
    request = SimpleNamespace(headers={"x-api-key": "explicit", "authorization": "Bearer ignored"})
    assert extract_calculate_api_key(request) == "explicit"


def test_extract_calculate_api_key_accepts_bearer_token():
    request = SimpleNamespace(headers={"authorization": "Bearer token-value"})
    assert extract_calculate_api_key(request) == "token-value"


def test_load_trusted_proxy_networks_cloudflare_keyword():
    networks = load_trusted_proxy_networks("cloudflare")
    assert len(networks) == len(CLOUDFLARE_IP_RANGES)


def test_load_trusted_proxy_networks_cloudflare_case_insensitive():
    networks = load_trusted_proxy_networks("Cloudflare")
    assert len(networks) == len(CLOUDFLARE_IP_RANGES)


def test_load_trusted_proxy_networks_cloudflare_mixed_with_custom():
    networks = load_trusted_proxy_networks("cloudflare,10.0.0.0/8")
    assert len(networks) == len(CLOUDFLARE_IP_RANGES) + 1
