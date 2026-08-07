import pytest

from anomaly_backend.passwords import DUMMY_HASH, hash_password, verify_password


def test_hash_round_trips_and_rejects_a_wrong_password() -> None:
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("Correct horse battery staple", encoded)
    assert not verify_password("", encoded)


def test_encoding_carries_its_own_cost_parameters() -> None:
    scheme, cost, block_size, parallelism, salt, digest = hash_password("pw").split("$")

    assert scheme == "scrypt"
    assert (int(cost), int(block_size), int(parallelism)) == (16384, 8, 1)
    assert salt and digest


def test_equal_passwords_hash_differently() -> None:
    # A shared salt would let identical passwords be spotted across rows.
    assert hash_password("same") != hash_password("same")


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "not-a-hash",
        "scrypt$16384$8$1$onlyfivefields",
        "scrypt$16384$8$1$aa$bb$cc",
        "bcrypt$16384$8$1$YWFhYQ==$YmJiYg==",
        "scrypt$notanumber$8$1$YWFhYQ==$YmJiYg==",
        "scrypt$16384$8$1$not base64$YmJiYg==",
        "scrypt$0$8$1$YWFhYQ==$YmJiYg==",
        "scrypt$12345$8$1$YWFhYQ==$YmJiYg==",
        "scrypt$16384$0$1$YWFhYQ==$YmJiYg==",
        "scrypt$16384$8$0$YWFhYQ==$YmJiYg==",
    ],
)
def test_malformed_hashes_verify_false_instead_of_raising(encoded: str) -> None:
    # A corrupted row must fail the login, not turn it into a 500.
    assert not verify_password("anything", encoded)


def test_an_oversized_cost_is_refused_rather_than_exhausting_memory() -> None:
    assert not verify_password("anything", "scrypt$1048576$8$1$YWFhYQ==$YmJiYg==")


def test_dummy_hash_is_well_formed_and_unguessable() -> None:
    # Unknown usernames are verified against this so their timing matches a real
    # account. It has to be a hash a real password cannot match.
    assert DUMMY_HASH.startswith("scrypt$")
    assert not verify_password("", DUMMY_HASH)
    assert not verify_password("password", DUMMY_HASH)
