"""Adversarial acceptance tests for authority release decision integrity."""
from copy import deepcopy
import json
import unittest

from pydantic import ValidationError

from loopos_authority.models import CreateReleaseInitiativeRequest
from test_authority import ApiTests, release_request, workspace_document


class ReleaseDecisionConsistencyTests(unittest.TestCase):
    def test_conflicting_embedded_decisions_are_rejected(self):
        changes = {
            'decision_id': 'different-decision',
            'status': 'passed',
            'decided_by': 'different-reviewer',
            'decided_at': '2026-07-24T12:00:00+00:00',
            'basis': 'Different evidence conclusion',
            'source_ref_ids': ['github-change-set'],
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                payload = release_request().model_dump(mode='json')
                payload['release_assurance']['decisions'][0][field] = value
                with self.assertRaises(ValidationError):
                    CreateReleaseInitiativeRequest.model_validate(payload)

    def test_embedded_decision_cannot_replace_missing_canonical_decision(self):
        payload = release_request().model_dump(mode='json')
        payload['release_assurance']['decisions'].pop(0)
        with self.assertRaises(ValidationError):
            CreateReleaseInitiativeRequest.model_validate(payload)

    def test_canonical_decision_can_be_referenced_without_embedded_copy(self):
        payload = release_request().model_dump(mode='json')
        for gate in payload['release_assurance']['gates']:
            gate.pop('last_decision')
        parsed = CreateReleaseInitiativeRequest.model_validate(payload)
        self.assertEqual(len(parsed.release_assurance['decisions']), 2)

    def test_matching_embedded_and_canonical_decisions_remain_valid(self):
        payload = release_request().model_dump(mode='json')
        self.assertEqual(CreateReleaseInitiativeRequest.model_validate(deepcopy(payload)).model_dump(mode='json'), payload)


class ReleaseDecisionApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ApiTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        response = self.fixture.client.put('/v1/workspaces/workspace-release',
            headers={**self.fixture.headers, 'if-none-match': '*'},
            json={'document': workspace_document('workspace-release')})
        self.assertEqual(response.status_code, 201)

    def test_conflicting_review_is_rejected_without_persistence(self):
        payload = release_request().model_dump(mode='json')
        payload['release_assurance']['decisions'][0]['decided_by'] = 'substituted-reviewer'
        response = self.fixture.client.post('/v1/release-initiatives',
            headers={**self.fixture.headers, 'idempotency-key': 'conflicting-review-test'}, json=payload)
        self.assertEqual(response.status_code, 422, response.text)
        records = self.fixture.client.get('/v1/release-initiatives', headers=self.fixture.headers)
        self.assertEqual(records.status_code, 200)
        self.assertEqual(records.json(), [])

    def test_consistent_draft_remains_recordable_and_fail_closed(self):
        response = self.fixture.client.post('/v1/release-initiatives',
            headers={**self.fixture.headers, 'idempotency-key': 'consistent-review-test'},
            json=release_request().model_dump(mode='json'))
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['readiness_verdict']['verdict'], 'NO_GO')

    def test_legacy_conflict_remains_readable_but_cannot_retain_go(self):
        fixture = self.fixture
        record = fixture.store.create_release_initiative(fixture.operator, release_request(), 'legacy-conflict-seed')
        assurance = deepcopy(record.release_assurance)
        assurance['decisions'][0]['decided_by'] = 'conflicting-legacy-reviewer'
        fixture.store.connection.execute(
            'UPDATE release_initiatives SET release_assurance_json = ?, readiness_verdict_json = ? WHERE initiative_id = ?',
            (json.dumps(assurance), json.dumps({'verdict': 'GO'}), record.initiative_id))
        response = fixture.client.get('/v1/release-initiatives', headers=fixture.headers)
        self.assertEqual(response.status_code, 200, response.text)
        stored = response.json()[0]
        self.assertEqual(stored['release_assurance'], assurance)
        self.assertEqual(stored['readiness_verdict']['verdict'], 'NO_GO')
        self.assertTrue(any('current gate decision' in reason for reason in stored['readiness_verdict']['failing_reasons']))
        proof = fixture.client.get(f'/v1/release-initiatives/{record.initiative_id}/proof-pack', headers=fixture.headers)
        self.assertEqual(proof.status_code, 200, proof.text)
        self.assertEqual(proof.json()['readiness_verdict']['verdict'], 'NO_GO')
