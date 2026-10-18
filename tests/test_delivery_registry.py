import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "delivery_registry", Path(__file__).parents[1] / "scripts" / "validate_delivery_registry.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DeliveryRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = {
            "schema_version": 1,
            "as_of": "2026-10-18",
            "projects": [{
                "id": "example", "kind": "product", "repository": "owner/example",
                "main_sha": "a" * 40, "ci": {"state": "unknown"},
                "deployment": {"state": "unknown", "sha": None},
                "acceptance": {"state": "not_verified"},
                "owns_domains": ["commercial_booking"],
            }],
        }

    def errors(self):
        return MODULE.validate_registry(self.registry)

    def test_unknown_deployment_is_valid_without_inventing_sha(self):
        self.assertEqual(self.errors(), [])

    def test_successful_ci_does_not_authorize_acceptance(self):
        project = self.registry["projects"][0]
        project["ci"] = {"state": "SUCCESS", "sha": "a" * 40,
                         "evidence_url": "https://github.com/owner/example/actions/runs/1"}
        project["acceptance"]["state"] = "accepted"
        self.assertTrue(any("evidenced gates" in error for error in self.errors()))

    def test_previous_runtime_observation_is_historical(self):
        self.registry["projects"][0]["deployment"] = {
            "state": "observed", "sha": "a" * 40,
            "observed_on": "2026-10-11", "evidence": "recorded-health.json",
        }
        self.assertTrue(any("historical" in error for error in self.errors()))

    def test_unknown_runtime_cannot_inherit_main_sha(self):
        self.registry["projects"][0]["deployment"]["sha"] = "a" * 40
        self.assertTrue(any("must not inherit" in error for error in self.errors()))

    def test_two_projects_cannot_own_the_same_booking_domain(self):
        second = copy.deepcopy(self.registry["projects"][0])
        second["id"] = "second"
        self.registry["projects"].append(second)
        self.assertTrue(any("canonical owner" in error for error in self.errors()))

    def test_url_credential_is_rejected_without_echoing_it(self):
        value = "private-placeholder-value"
        self.registry["note"] = "https://" + value + "@github.com/owner/example"
        errors = self.errors()
        self.assertTrue(any("URL credentials" in error for error in errors))
        self.assertNotIn(value, " ".join(errors))

    def test_token_in_a_mapping_key_is_also_rejected(self):
        # Keys are data too; callers must not leak values through error paths.
        value = "gh" + "p_" + "a" * 36
        self.registry[value] = "note"
        self.assertTrue(MODULE.validate_registry(self.registry))

    def test_successful_ci_requires_sha_and_link(self):
        self.registry["projects"][0]["ci"] = {"state": "SUCCESS"}
        self.assertTrue(any("full commit SHA" in error for error in self.errors()))

    def test_evidenced_independent_acceptance_is_allowed(self):
        self.registry["projects"][0]["acceptance"] = {
            "state": "accepted", "accepted_by": "independent-reviewer",
            "accepted_on": "2026-10-18",
            "gates": [{"passed": True, "evidence": "acceptance-1.json"}],
        }
        self.assertEqual(self.errors(), [])


if __name__ == "__main__":
    unittest.main()
