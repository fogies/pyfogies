"""Test Terraform network module."""

from fogies.terraform.network import NetworkOutput


def test_network_output(pyfogies_test_network: NetworkOutput) -> None:
    """Network module creates VPC and subnets with expected output."""
    assert pyfogies_test_network.vpc_id.startswith("vpc-")

    assert len(pyfogies_test_network.subnet_ids) == 2
    assert all(sid.startswith("subnet-") for sid in pyfogies_test_network.subnet_ids)

    assert len(pyfogies_test_network.availability_zone_to_subnet_id) == 2
    assert set(pyfogies_test_network.availability_zone_to_subnet_id.values()) == set(
        pyfogies_test_network.subnet_ids
    )
