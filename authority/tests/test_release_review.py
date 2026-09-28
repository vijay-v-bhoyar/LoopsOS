"""Real local API review journey with signed synthetic GitHub check fixtures.

These fixtures are local test evidence, not real provider or organizational proof.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from threading import Event
import unittest
import uuid
from unittest.mock import patch

from loopos_authority.models import Actor, ReleaseReviewRequest
from loopos_authority.release_policy import release_policy
from loopos_authority.store import Conflict, Forbidden
import test_authority as fixtures
from test_authority import release_request, workspace_document, json_bytes, webhook_signature


def seed_reviewable_release(client, headers, *, tenant='tenant-api', secret='github-webhook-secret', workspace_id='workspace-release', create=True,
                            app_id=4242, workflow_id=7007, include_workflow=True, workflow_rerun_conclusion=None):
    """Reusable TestClient/httpx.Client seed: actual local API and signed fixtures."""
    policy_response = client.get('/v1/release-policy', headers=headers)
    policy_response.raise_for_status()
    policy = policy_response.json()
    workspace = client.put(f'/v1/workspaces/{workspace_id}', headers={**headers, 'if-none-match': '*'}, json={'document': workspace_document(workspace_id)})
    if workspace.status_code not in (201, 409, 412):
        workspace.raise_for_status()
    now = datetime.now(timezone.utc).isoformat()
    nonce = uuid.uuid4().hex
    payload = release_request().model_dump(mode='json')
    payload['workspace_id'] = workspace_id
    profile = payload['release_assurance']
    profile.update(policy_id=policy['policy_id'], policy_version=policy['version'], policy_digest=policy['policy_digest'],
                   release_subject={'repository': 'local-fixture/release', 'commit_sha': 'd' * 40},
                   gates=[], decisions=[], evidence_artifacts=[], external_refs=[], exceptions=[])
    payload['loop_bundle_ids'] = [requirement['loop_id'] for requirement in policy['requirements']]
    payload['source_event_ids'] = []
    for index, requirement in enumerate(policy['requirements']):
        loop_id, check_name = requirement['loop_id'], requirement['check_name']
        check_suite_id = 900_000 + index
        check = {'repository': {'full_name': 'local-fixture/release'}, 'check_run': {
            'id': f'{nonce}-{loop_id}', 'name': check_name, 'status': 'completed', 'conclusion': 'success',
            'head_sha': 'd' * 40, 'completed_at': now, 'started_at': now,
            'app': {'id': app_id}, 'check_suite': {'id': check_suite_id},
            'html_url': f'https://github.example/local-fixture/release/checks/{nonce}-{loop_id}',
        }}
        body = json_bytes(check)
        response = client.post(f'/v1/webhooks/{tenant}/github?workspace_id={workspace_id}', content=body,
            headers={'x-hub-signature-256': webhook_signature(secret, body), 'x-github-event': 'check_run',
                     'x-github-delivery': f'{nonce}-{loop_id}', 'content-type': 'application/json'})
        response.raise_for_status()
        event = response.json()
        event_id = event['connector_event_id']
        payload['source_event_ids'].append(event_id)
        workflow_events = []
        if include_workflow:
            workflow_states = ['success']
            if workflow_rerun_conclusion:
                workflow_states.append(workflow_rerun_conclusion)
            for attempt, conclusion in enumerate(workflow_states, start=1):
                workflow_payload = {
                    'repository': {'full_name': 'local-fixture/release'},
                    'workflow': {'id': workflow_id, 'name': 'Protected Release Workflow'},
                    'workflow_run': {
                        'id': check_suite_id + 10_000, 'workflow_id': workflow_id,
                        'check_suite_id': check_suite_id, 'run_attempt': attempt,
                        'head_sha': 'd' * 40, 'status': 'completed', 'conclusion': conclusion,
                        'created_at': now, 'updated_at': now,
                        'html_url': f'https://github.example/local-fixture/release/actions/runs/{check_suite_id + 10_000}',
                    },
                }
                workflow_body = json_bytes(workflow_payload)
                workflow_response = client.post(f'/v1/webhooks/{tenant}/github?workspace_id={workspace_id}', content=workflow_body,
                    headers={'x-hub-signature-256': webhook_signature(secret, workflow_body), 'x-github-event': 'workflow_run',
                             'x-github-delivery': f'{nonce}-{loop_id}-workflow-{attempt}', 'content-type': 'application/json'})
                workflow_response.raise_for_status()
                workflow_events.append(workflow_response.json())
                payload['source_event_ids'].append(workflow_events[-1]['connector_event_id'])
        gate_id = f'gate-{loop_id}'
        decision = {'decision_id': f'claim-{loop_id}', 'gate_id': gate_id, 'status': 'passed',
                    'decided_by': 'fixture-producer-claim', 'decided_at': now, 'basis': 'Observed successful protected check.', 'source_ref_ids': [event_id]}
        profile['gates'].append({'gate_id': gate_id, 'label': check_name, 'loop_id': loop_id, 'control_ids': [loop_id],
                                'required_evidence': [check_name], 'status': 'passed', 'blocker': '', 'last_decision': deepcopy(decision)})
        profile['decisions'].append(decision)
        profile['external_refs'].append({'ref_id': event_id, 'system': 'github', 'object_type': 'check', 'label': check_name,
                                         'observed_at': event['observed_at'], 'evidence_hash': event['payload_hash']})
        profile['evidence_artifacts'].append({'artifact_id': f'artifact-{loop_id}', 'gate_id': gate_id, 'loop_id': loop_id,
                                            'source_ref': event_id, 'label': check_name, 'freshness': 'fresh', 'required': True,
                                            'observed_at': event['observed_at']})
    if not create:
        return payload
    response = client.post('/v1/release-initiatives', headers={**headers, 'idempotency-key': f'seed-{nonce}'}, json=payload)
    response.raise_for_status()
    return response.json()


def review_payload(record, decision='approve'):
    return {**{field: record['review_context'][field] for field in ('subject_digest', 'policy_digest', 'evidence_digest')},
            'previous_review_id': (record['review_context'].get('latest_review') or {}).get('review_id'),
            'decision': decision, 'basis': 'Independent local review of every protected check and exact commit.'}


class ReleaseReviewTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ApiTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        session = self.f.client.post('/v1/dev/sessions', json={'tenant_id': 'tenant-api', 'user_id': 'release-reviewer', 'name': 'Reviewer', 'role': 'Approver'}).json()
        self.reviewer = {'authorization': f"Bearer {session['access_token']}"}

    def seed(self):
        return seed_reviewable_release(self.f.client, self.f.headers)

    def test_reviewability_requires_approved_check_app_and_workflow_evidence(self):
        cases = (
            ('unapproved app', {'app_id': 4243}, 'publisher'),
            ('unapproved workflow', {'workflow_id': 7008}, 'approved workflow'),
            ('missing workflow', {'include_workflow': False}, 'approved workflow'),
            ('failed latest rerun', {'workflow_rerun_conclusion': 'failure'}, 'approved workflow'),
        )
        for name, kwargs, reason in cases:
            with self.subTest(case=name):
                record = seed_reviewable_release(self.f.client, self.f.headers, **kwargs)
                self.assertEqual(record['readiness_verdict']['verdict'], 'NO_GO')
                self.assertFalse(record['review_context']['reviewable'])
                self.assertIn(reason, ' '.join(record['review_context']['blocking_reasons']))
                self.assertEqual(self.review(record).status_code, 409)

    def test_release_policy_digest_changes_with_approved_publisher_identity(self):
        base = release_policy(4242, (7007,))
        changed_app = release_policy(4243, (7007,))
        changed_workflow = release_policy(4242, (7008,))
        self.assertNotEqual(base['policy_digest'], changed_app['policy_digest'])
        self.assertNotEqual(base['policy_digest'], changed_workflow['policy_digest'])

    def test_corrupt_workflow_payload_cannot_reuse_an_older_success(self):
        payload = seed_reviewable_release(self.f.client, self.f.headers, create=False)
        workflow_event_id = payload['source_event_ids'][1]
        self.f.store.connection.execute(
            "UPDATE connector_events SET payload_json = 'not-json' WHERE connector_event_id = ?",
            (workflow_event_id,),
        )
        self.f.store.connection.commit()
        created = self.f.client.post('/v1/release-initiatives',
            headers={**self.f.headers, 'idempotency-key': f'corrupt-workflow-{uuid.uuid4().hex}'}, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        record = created.json()
        self.assertEqual(record['readiness_verdict']['verdict'], 'NO_GO')
        self.assertFalse(record['review_context']['reviewable'])
        self.assertIn('approved workflow', ' '.join(record['review_context']['blocking_reasons']))

    def assert_malformed_check_payload_blocks_release(self, malformed_payload):
        record = self.seed()
        check_event_id = record['source_event_ids'][0]
        self.f.store.connection.execute(
            'UPDATE connector_events SET payload_json = ? WHERE connector_event_id = ?',
            (malformed_payload, check_event_id),
        )
        self.f.store.connection.commit()

        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])

        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertFalse(refreshed.review_context['reviewable'])
        self.assertIn('observed check', ' '.join(refreshed.review_context['blocking_reasons']))

    def test_corrupt_check_payload_fails_closed_without_crashing(self):
        self.assert_malformed_check_payload_blocks_release('not-json')

    def test_non_object_check_payload_fails_closed_without_crashing(self):
        self.assert_malformed_check_payload_blocks_release('[]')

    def test_invalid_check_payload_shape_fails_closed_without_crashing(self):
        self.assert_malformed_check_payload_blocks_release('{"repository":{},"check_run":null}')

    def test_unlinked_malformed_tenant_check_revokes_go(self):
        record = self.seed()
        approved = self.review(record)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['readiness_verdict']['verdict'], 'GO')

        body = json_bytes({'repository': {'full_name': 'local-fixture/release'}})
        response = self.f.client.post(
            '/v1/webhooks/tenant-api/github?workspace_id=workspace-release',
            content=body,
            headers={
                'x-hub-signature-256': webhook_signature('github-webhook-secret', body),
                'x-github-event': 'check_run',
                'x-github-delivery': f'malformed-unlinked-check-{uuid.uuid4().hex}',
                'content-type': 'application/json',
            },
        )
        response.raise_for_status()

        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])

        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertFalse(refreshed.review_context['reviewable'])
        self.assertIn('observed check', ' '.join(refreshed.review_context['blocking_reasons']))

    def test_malformed_check_for_known_other_repository_does_not_revoke_go(self):
        record = self.seed()
        approved = self.review(record)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['readiness_verdict']['verdict'], 'GO')

        body = json_bytes({'repository': {'full_name': 'other-org/unrelated-repository'}})
        response = self.f.client.post(
            '/v1/webhooks/tenant-api/github?workspace_id=workspace-release',
            content=body,
            headers={
                'x-hub-signature-256': webhook_signature('github-webhook-secret', body),
                'x-github-event': 'check_run',
                'x-github-delivery': f'malformed-other-repository-{uuid.uuid4().hex}',
                'content-type': 'application/json',
            },
        )
        response.raise_for_status()

        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
        self.assertEqual(refreshed.readiness_verdict['verdict'], 'GO')
        self.assertTrue(refreshed.review_context['reviewable'], refreshed.review_context)

    def test_path_like_repository_identity_does_not_prove_unrelated_scope(self):
        record = self.seed()
        approved = self.review(record)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['readiness_verdict']['verdict'], 'GO')

        body = json_bytes({'repository': {'full_name': '../unrelated-repository'}})
        response = self.f.client.post(
            '/v1/webhooks/tenant-api/github?workspace_id=workspace-release',
            content=body,
            headers={
                'x-hub-signature-256': webhook_signature('github-webhook-secret', body),
                'x-github-event': 'check_run',
                'x-github-delivery': f'path-like-repository-{uuid.uuid4().hex}',
                'content-type': 'application/json',
            },
        )
        response.raise_for_status()
        event_id = response.json()['connector_event_id']
        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])

        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertIn(event_id, refreshed.review_context['blocking_observed_check_event_ids'])

    def test_malformed_matching_check_exposes_blocking_event_id(self):
        record = self.seed()
        body = json_bytes({'repository': {'full_name': 'local-fixture/release'}})
        response = self.f.client.post(
            '/v1/webhooks/tenant-api/github?workspace_id=workspace-release',
            content=body,
            headers={
                'x-hub-signature-256': webhook_signature('github-webhook-secret', body),
                'x-github-event': 'check_run',
                'x-github-delivery': f'malformed-matching-check-{uuid.uuid4().hex}',
                'content-type': 'application/json',
            },
        )
        response.raise_for_status()
        event_id = response.json()['connector_event_id']

        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertIn(event_id, refreshed.review_context['blocking_observed_check_event_ids'])

    def test_signed_failed_check_without_head_sha_must_revoke_go(self):
        record = self.seed()
        approved = self.review(record)
        self.assertEqual(approved.status_code, 200, approved.text)
        from datetime import datetime, timezone
        body = json_bytes({
            'repository': {'full_name': 'local-fixture/release'},
            'check_run': {'name': 'malformed-without-commit', 'status': 'completed', 'conclusion': 'failure',
                          'completed_at': datetime.now(timezone.utc).isoformat()},
        })
        response = self.f.client.post(
            '/v1/webhooks/tenant-api/github?workspace_id=workspace-release',
            content=body,
            headers={
                'x-hub-signature-256': webhook_signature('github-webhook-secret', body),
                'x-github-event': 'check_run',
                'x-github-delivery': f'missing-head-sha-acceptance-{uuid.uuid4().hex}',
                'content-type': 'application/json',
            },
        )
        response.raise_for_status()
        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertIn('observed check', ' '.join(refreshed.review_context['blocking_reasons']))

    def test_failed_check_for_valid_different_commit_does_not_revoke_go(self):
        record = self.seed()
        approved = self.review(record)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['readiness_verdict']['verdict'], 'GO')
        from datetime import datetime, timezone
        body = json_bytes({
            'repository': {'full_name': 'local-fixture/release'},
            'check_run': {'name': 'other-commit', 'head_sha': 'e' * 40, 'status': 'completed', 'conclusion': 'failure',
                          'completed_at': datetime.now(timezone.utc).isoformat()},
        })
        response = self.f.client.post(
            '/v1/webhooks/tenant-api/github?workspace_id=workspace-release',
            content=body,
            headers={
                'x-hub-signature-256': webhook_signature('github-webhook-secret', body),
                'x-github-event': 'check_run',
                'x-github-delivery': f'other-commit-{uuid.uuid4().hex}',
                'content-type': 'application/json',
            },
        )
        response.raise_for_status()
        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
        self.assertEqual(refreshed.readiness_verdict['verdict'], 'GO')

    def review(self, record, *, headers=None, decision='approve', key=None, payload=None):
        return self.f.client.post(f"/v1/release-initiatives/{record['initiative_id']}/reviews",
            headers={**(headers or self.reviewer), 'idempotency-key': key or f'review-{uuid.uuid4().hex}'}, json=payload or review_payload(record, decision))

    def test_complete_signed_evidence_requires_real_separate_review_and_survives_reopen(self):
        record = self.seed()
        self.assertEqual(record['readiness_verdict']['verdict'], 'REVIEW_REQUIRED')
        self.assertTrue(record['review_context']['reviewable'], record['review_context'])
        approved = self.review(record, key='review-positive-key')
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['readiness_verdict']['verdict'], 'GO')
        review = approved.json()['review_context']['latest_review']
        self.assertEqual(review['reviewer_id'], 'release-reviewer')
        self.assertNotEqual(review['reviewer_id'], record['created_by'])
        replay = self.review(record, key='review-positive-key')
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()['review_context']['latest_review']['review_id'], review['review_id'])
        self.assertEqual(self.f.store.connection.execute('SELECT count(*) FROM audit_events WHERE event_type=?', (f"RELEASE_REVIEW:{record['initiative_id']}",)).fetchone()[0], 1)
        # A second connection reads only committed durable state.
        from loopos_authority.store import AuthorityStore
        reopened = AuthorityStore(self.f.app.state.settings.database_path, self.f.store.corpus)
        reopened.github_release_attestor_app_id = self.f.app.state.settings.github_release_attestor_app_id
        reopened.github_release_workflow_ids = self.f.app.state.settings.github_release_workflow_ids
        self.assertTrue(reopened.activate_release_policy(release_policy(
            reopened.github_release_attestor_app_id,
            reopened.github_release_workflow_ids,
            policy_epoch=self.f.app.state.settings.release_policy_epoch,
        )))
        try:
            durable = reopened.get_release_initiative('tenant-api', record['initiative_id'])
            self.assertEqual(durable.readiness_verdict['verdict'], 'GO')
        finally:
            reopened.close()
        proof = self.f.client.get(f"/v1/release-initiatives/{record['initiative_id']}/proof-pack", headers=self.reviewer)
        self.assertEqual(proof.json()['readiness_verdict']['verdict'], 'GO')
        self.assertIn(review['review_id'], proof.json()['markdown'])
        self.assertTrue(self.f.store.verify_audit_chain('tenant-api')[0])

    def test_old_worker_loses_go_when_new_policy_epoch_activates(self):
        record = self.seed()
        approved = self.review(record, key='epoch-fence-review-key').json()
        self.assertEqual(approved['readiness_verdict']['verdict'], 'GO')

        from loopos_authority.store import AuthorityStore
        settings = self.f.app.state.settings
        newer_worker = AuthorityStore(settings.database_path, self.f.store.corpus)
        newer_worker.github_release_attestor_app_id = settings.github_release_attestor_app_id
        newer_worker.github_release_workflow_ids = settings.github_release_workflow_ids
        self.addCleanup(newer_worker.close)
        self.assertTrue(newer_worker.activate_release_policy(release_policy(
            settings.github_release_attestor_app_id,
            settings.github_release_workflow_ids,
            policy_epoch=settings.release_policy_epoch + 1,
        )))

        self.assertFalse(self.f.store.release_policy_is_current())
        stale = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
        self.assertEqual(stale.readiness_verdict['verdict'], 'NO_GO')
        self.assertFalse(stale.review_context['reviewable'])
        self.assertIn('fenced', ' '.join(stale.readiness_verdict['failing_reasons']).lower())
        self.assertEqual(self.f.client.get('/v1/release-policy', headers=self.f.headers).status_code, 503)
        self.assertEqual(self.f.client.get('/health/ready').status_code, 503)
        self.assertEqual(self.review(approved, key='stale-worker-review-key').status_code, 409)
        self.assertEqual(
            self.f.store.connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE event_type = 'RELEASE_POLICY_EPOCH_ACTIVATED'"
            ).fetchone()[0],
            2,
        )

    def test_evaluator_change_at_same_epoch_fences_old_worker_and_recovers_at_new_epoch(self):
        import loopos_authority.release_policy as policy_module
        from loopos_authority.store import AuthorityStore

        record = self.seed()
        approved = self.review(record, key='same-epoch-evaluator-change-key').json()
        self.assertEqual(approved['readiness_verdict']['verdict'], 'GO')
        settings = self.f.app.state.settings
        old_worker = self.f.store
        new_digest = hashlib.sha256(b'next release evaluator snapshot').hexdigest()

        newer_worker = AuthorityStore(settings.database_path, self.f.store.corpus)
        newer_worker.github_release_attestor_app_id = settings.github_release_attestor_app_id
        newer_worker.github_release_workflow_ids = settings.github_release_workflow_ids
        self.addCleanup(newer_worker.close)

        with patch.object(policy_module, '_EVALUATOR_DIGEST', new_digest):
            # A deployment that forgot to advance its configured epoch must
            # fence all workers instead of leaving the prior worker green.
            self.assertFalse(newer_worker.activate_release_policy(release_policy(
                settings.github_release_attestor_app_id,
                settings.github_release_workflow_ids,
                policy_epoch=settings.release_policy_epoch,
            )))

        stale = old_worker.get_release_initiative('tenant-api', record['initiative_id'])
        self.assertEqual(stale.readiness_verdict['verdict'], 'NO_GO')
        self.assertFalse(stale.readiness_verdict['policy_fence']['current'])
        self.assertEqual(
            old_worker.connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE event_type = 'RELEASE_POLICY_EPOCH_FENCED'"
            ).fetchone()[0],
            1,
        )

        with patch.object(policy_module, '_EVALUATOR_DIGEST', new_digest):
            # The operator's next epoch is one above the durable fence marker.
            self.assertTrue(newer_worker.activate_release_policy(release_policy(
                settings.github_release_attestor_app_id,
                settings.github_release_workflow_ids,
                policy_epoch=settings.release_policy_epoch + 2,
            )))
        self.assertTrue(newer_worker.release_policy_is_current())
        self.assertEqual(
            old_worker.get_release_initiative('tenant-api', record['initiative_id']).readiness_verdict['verdict'],
            'NO_GO',
        )

        policy_doc = (fixtures.REPO_ROOT / 'authority/RELEASE_REVIEW.md').read_text(encoding='utf-8')
        self.assertIn('RELEASE_POLICY_EPOCH_FENCED', policy_doc)
        self.assertIn('greater than the fence marker', policy_doc)

    def test_release_policy_epoch_cannot_roll_back_or_change_in_place(self):
        from loopos_authority.store import AuthorityStore
        settings = self.f.app.state.settings
        newer_worker = AuthorityStore(settings.database_path, self.f.store.corpus)
        self.addCleanup(newer_worker.close)
        newer_worker.github_release_attestor_app_id = settings.github_release_attestor_app_id
        newer_worker.github_release_workflow_ids = settings.github_release_workflow_ids
        epoch_two = release_policy(
            settings.github_release_attestor_app_id,
            settings.github_release_workflow_ids,
            policy_epoch=settings.release_policy_epoch + 1,
        )
        self.assertTrue(newer_worker.activate_release_policy(epoch_two))

        self.assertFalse(self.f.store.activate_release_policy(release_policy(
            settings.github_release_attestor_app_id,
            settings.github_release_workflow_ids,
            policy_epoch=settings.release_policy_epoch,
        )))
        self.assertFalse(self.f.store.release_policy_is_current())
        with self.assertRaisesRegex(Exception, 'monotonic'):
            newer_worker.connection.execute('UPDATE release_policy_control SET epoch = ? WHERE singleton = 1', (settings.release_policy_epoch,))
        with self.assertRaisesRegex(Exception, 'monotonic'):
            newer_worker.connection.execute("UPDATE release_policy_control SET policy_digest = ? WHERE singleton = 1", ('0' * 64,))
        with self.assertRaisesRegex(Exception, 'cannot be deleted'):
            newer_worker.connection.execute('DELETE FROM release_policy_control WHERE singleton = 1')

        conflicting_worker = AuthorityStore(settings.database_path, self.f.store.corpus)
        self.addCleanup(conflicting_worker.close)
        conflicting_worker.github_release_attestor_app_id = settings.github_release_attestor_app_id
        conflicting_worker.github_release_workflow_ids = settings.github_release_workflow_ids
        self.assertFalse(conflicting_worker.activate_release_policy(release_policy(
            settings.github_release_attestor_app_id + 1,
            settings.github_release_workflow_ids,
            policy_epoch=settings.release_policy_epoch + 1,
        )))
        self.assertFalse(conflicting_worker.release_policy_is_current())
        self.assertFalse(newer_worker.release_policy_is_current())
        self.assertEqual(
            newer_worker.connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE event_type = 'RELEASE_POLICY_EPOCH_FENCED'"
            ).fetchone()[0],
            1,
        )
        self.assertTrue(newer_worker.activate_release_policy(release_policy(
            settings.github_release_attestor_app_id,
            settings.github_release_workflow_ids,
            policy_epoch=settings.release_policy_epoch + 3,
        )))
        self.assertTrue(newer_worker.release_policy_is_current())

    def test_policy_activation_serializes_after_in_flight_readiness_evaluation(self):
        record = self.seed()
        self.assertEqual(self.review(record, key='epoch-linearization-key').json()['readiness_verdict']['verdict'], 'GO')
        from loopos_authority.store import AuthorityStore
        settings = self.f.app.state.settings
        newer_worker = AuthorityStore(settings.database_path, self.f.store.corpus)
        newer_worker.github_release_attestor_app_id = settings.github_release_attestor_app_id
        newer_worker.github_release_workflow_ids = settings.github_release_workflow_ids
        self.addCleanup(newer_worker.close)

        evaluation_started = Event()
        finish_evaluation = Event()
        activation_attempted = Event()
        read_store = self.f.store
        read_initiative = read_store._release_observed_checks

        def pause_during_evaluation(initiative):
            evaluation_started.set()
            if not finish_evaluation.wait(5):
                raise TimeoutError('timed out waiting to finish the in-flight policy evaluation')
            return read_initiative(initiative)

        next_policy = release_policy(
            settings.github_release_attestor_app_id,
            settings.github_release_workflow_ids,
            policy_epoch=settings.release_policy_epoch + 1,
        )
        with patch.object(read_store, '_release_observed_checks', side_effect=pause_during_evaluation):
            with ThreadPoolExecutor(max_workers=2) as pool:
                evaluation = pool.submit(read_store.get_release_initiative, 'tenant-api', record['initiative_id'])
                self.assertTrue(evaluation_started.wait(5), 'readiness evaluation did not reach the protected section')

                def activate_after_attempt_signal():
                    activation_attempted.set()
                    return newer_worker.activate_release_policy(next_policy)

                activation = pool.submit(activate_after_attempt_signal)
                self.assertTrue(activation_attempted.wait(5))
                self.assertFalse(activation.done(), 'policy promotion crossed an in-flight shared epoch lock')
                finish_evaluation.set()
                self.assertEqual(evaluation.result(timeout=5).readiness_verdict['verdict'], 'GO')
                self.assertTrue(activation.result(timeout=5))

        self.assertEqual(
            read_store.get_release_initiative('tenant-api', record['initiative_id']).readiness_verdict['verdict'],
            'NO_GO',
        )

    def test_release_epoch_migration_is_additive_and_private_from_browser_roles(self):
        migration = (fixtures.REPO_ROOT / 'supabase/migrations/20260921040000_release_policy_epoch_fence.sql').read_text(encoding='utf-8')
        normalized = migration.lower()
        self.assertIn('create table if not exists release_policy_control', normalized)
        self.assertIn('epoch bigint not null check (epoch > 0)', normalized)
        self.assertIn('alter table release_policy_control enable row level security', normalized)
        self.assertIn("rolname in ('anon', 'authenticated')", normalized)
        self.assertIn('revoke all on release_policy_control', normalized)
        self.assertIn('release_policy_control_monotonic', normalized)
        self.assertIn('release_policy_control_no_delete', normalized)
        self.assertIn('release_policy_control_no_truncate', normalized)
        self.assertNotRegex(normalized, r'(?m)^\s*(drop|truncate|delete\s+from)\b', msg='the migration must not delete existing data or schema')

    def test_actor_scope_role_separation_and_forged_review_fields(self):
        record = self.seed()
        self.assertEqual(self.review(record, headers=self.f.headers).status_code, 403)
        same = self.f.client.post('/v1/dev/sessions', json={'tenant_id': 'tenant-api', 'user_id': 'operator', 'name': 'Same Producer', 'role': 'Approver'}).json()
        self.assertEqual(self.review(record, headers={'authorization': f"Bearer {same['access_token']}"}).status_code, 403)
        other = self.f.client.post('/v1/dev/sessions', json={'tenant_id': 'other-tenant', 'user_id': 'reviewer', 'name': 'Other', 'role': 'Approver'}).json()
        self.assertEqual(self.review(record, headers={'authorization': f"Bearer {other['access_token']}"}).status_code, 404)
        forged = {**review_payload(record), 'reviewer_id': 'executive', 'reviewed_at': '2000-01-01T00:00:00Z'}
        self.assertEqual(self.review(record, payload=forged).status_code, 422)

    def test_protected_denominator_and_artifact_mutations_never_reviewable(self):
        original = seed_reviewable_release(self.f.client, self.f.headers, create=False)
        mutations = ['omit-gate-and-bundle', 'missing-artifact', 'optional-artifact', 'missing-declaration', 'stale-artifact',
                     'bad-source-hash', 'wrong-subject', 'unknown-policy', 'forged-time', 'extra-required-artifact', 'extra-required-declaration', 'closed-exception', 'expired-exception']
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                payload = deepcopy(original)
                profile = payload['release_assurance']
                gate = profile['gates'][0]
                if mutation == 'omit-gate-and-bundle':
                    removed = profile['gates'].pop(0)
                    payload['loop_bundle_ids'].remove(removed['loop_id'])
                    profile['decisions'] = [item for item in profile['decisions'] if item['gate_id'] != removed['gate_id']]
                    profile['evidence_artifacts'] = [item for item in profile['evidence_artifacts'] if item['gate_id'] != removed['gate_id']]
                elif mutation == 'missing-artifact': profile['evidence_artifacts'].pop(0)
                elif mutation == 'optional-artifact': profile['evidence_artifacts'][0]['required'] = False
                elif mutation == 'missing-declaration': gate['required_evidence'] = []
                elif mutation == 'extra-required-declaration': gate['required_evidence'].append('independent-extra-required-check')
                elif mutation == 'stale-artifact': profile['evidence_artifacts'][0]['observed_at'] = '2000-01-01T00:00:00Z'
                elif mutation == 'bad-source-hash': profile['external_refs'][0]['evidence_hash'] = '0' * 64
                elif mutation == 'wrong-subject': profile['release_subject']['commit_sha'] = 'e' * 40
                elif mutation == 'unknown-policy': profile['policy_digest'] = '0' * 64
                elif mutation == 'forged-time':
                    gate['last_decision']['decided_at'] = 'not-a-timestamp'
                    profile['decisions'][0]['decided_at'] = 'not-a-timestamp'
                elif mutation == 'extra-required-artifact':
                    extra = deepcopy(profile['evidence_artifacts'][0])
                    extra.update(artifact_id='unknown-required-artifact', label='Unobserved extra evidence')
                    profile['evidence_artifacts'].append(extra)
                else:
                    profile['exceptions'] = [{'exception_id': 'forged-exception', 'gate_id': gate['gate_id'], 'reason': 'Unaddressed rollback risk', 'approver': 'unverified-executive', 'expires_at': '2000-01-01T00:00:00Z', 'compensating_controls': [], 'status': 'closed' if mutation == 'closed-exception' else 'active'}]
                created = self.f.client.post('/v1/release-initiatives', headers={**self.f.headers, 'idempotency-key': f'mutant-{mutation}'}, json=payload)
                self.assertEqual(created.status_code, 201, created.text)
                record = created.json()
                self.assertEqual(record['readiness_verdict']['verdict'], 'NO_GO')
                self.assertFalse(record['review_context']['reviewable'])
                self.assertEqual(self.review(record).status_code, 409)

    def test_new_record_cannot_erase_same_commit_exception_history(self):
        approved = self.review(self.seed()).json()
        payload = seed_reviewable_release(self.f.client, self.f.headers, create=False)
        profile = payload['release_assurance']
        profile['exceptions'] = [{'exception_id': 'known-risk', 'gate_id': profile['gates'][0]['gate_id'], 'reason': 'Rollback proof is invalid', 'approver': 'unverified-person', 'expires_at': '2000-01-01T00:00:00Z', 'compensating_controls': [], 'status': 'closed'}]
        declared = self.f.client.post('/v1/release-initiatives', headers={**self.f.headers, 'idempotency-key': 'declared-known-risk'}, json=payload)
        self.assertEqual(declared.status_code, 201, declared.text)
        refreshed = self.f.store.get_release_initiative('tenant-api', approved['initiative_id'])
        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertIn('history', ' '.join(refreshed.review_context['blocking_reasons']))
        copy = self.seed()
        self.assertFalse(copy['review_context']['reviewable'])
        self.assertEqual(self.review(copy).status_code, 409)

    def test_newer_unselected_provider_failure_revokes_go_across_workspaces(self):
        approved = self.review(self.seed()).json()
        self.assertEqual(approved['readiness_verdict']['verdict'], 'GO')
        workspace_id = 'other-workspace-for-same-commit'
        self.f.client.put(f'/v1/workspaces/{workspace_id}', headers={**self.f.headers, 'if-none-match': '*'}, json={'document': workspace_document(workspace_id)}).raise_for_status()
        original_event = self.f.store.connection.execute('SELECT payload_json FROM connector_events WHERE connector_event_id=?', (approved['source_event_ids'][0],)).fetchone()
        failure = json.loads(original_event['payload_json'])
        failure['repository']['full_name'] = 'LOCAL-FIXTURE/release'
        failure['check_run'].update(id='new-failed-check', conclusion='failure', completed_at=datetime.now(timezone.utc).isoformat(), html_url='https://github.example/failed-new-check')
        body = json_bytes(failure)
        response = self.f.client.post(f'/v1/webhooks/tenant-api/github?workspace_id={workspace_id}', content=body, headers={
            'x-hub-signature-256': webhook_signature('github-webhook-secret', body), 'x-github-event': 'check_run', 'x-github-delivery': 'new-unselected-failure', 'content-type': 'application/json'})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertNotIn(response.json()['connector_event_id'], approved['source_event_ids'])
        refreshed = self.f.store.get_release_initiative('tenant-api', approved['initiative_id'])
        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertFalse(refreshed.review_context['reviewable'])
        self.assertNotEqual(refreshed.review_context['evidence_digest'], approved['review_context']['evidence_digest'])
        self.assertEqual(self.review(approved).status_code, 409)
        self.assertIn('adverse', ' '.join(refreshed.readiness_verdict['failing_reasons']))
        proof = self.f.client.get(f"/v1/release-initiatives/{approved['initiative_id']}/proof-pack", headers=self.reviewer)
        self.assertEqual(proof.json()['readiness_verdict']['verdict'], 'NO_GO')
        # A late delivery of an older success cannot hide the later failure.
        old_success = json.loads(original_event['payload_json'])
        old_success['check_run'].update(id='late-old-success', html_url='https://github.example/late-old-success')
        body = json_bytes(old_success)
        response = self.f.client.post('/v1/webhooks/tenant-api/github?workspace_id=workspace-release', content=body, headers={
            'x-hub-signature-256': webhook_signature('github-webhook-secret', body), 'x-github-event': 'check_run', 'x-github-delivery': 'late-old-success', 'content-type': 'application/json'})
        self.assertEqual(response.status_code, 201, response.text)
        current = self.f.store.get_release_initiative('tenant-api', approved['initiative_id'])
        self.assertEqual(current.readiness_verdict['verdict'], 'NO_GO')
        self.assertIn('adverse', ' '.join(current.readiness_verdict['failing_reasons']))
        recovered = self.seed()
        self.assertTrue(recovered['review_context']['reviewable'], recovered['review_context'])
        self.assertEqual(self.review(recovered).json()['readiness_verdict']['verdict'], 'GO')
        self.assertEqual(self.f.store.get_release_initiative('tenant-api', approved['initiative_id']).readiness_verdict['verdict'], 'NO_GO')

    def test_review_digest_conflicts_and_read_time_expiry(self):
        record = self.seed()
        for key in ('subject_digest', 'policy_digest', 'evidence_digest'):
            payload = {**review_payload(record), key: '0' * 64}
            self.assertEqual(self.review(record, payload=payload).status_code, 409)
        approved = self.review(record, key='immutable-review-retry').json()
        self.assertEqual(approved['readiness_verdict']['verdict'], 'GO')
        self.assertEqual(self.review(record, decision='reject', key='immutable-review-retry').status_code, 409)
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        with patch('loopos_authority.store.utc_now', return_value=future):
            refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
            self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
            self.assertIn('expired', ' '.join(refreshed.readiness_verdict['review_reasons']))

    def test_rejection_and_changed_evidence_revoke_go(self):
        record = self.seed()
        approved = self.review(record, key='first-approval-before-veto').json()
        rejected = self.review(approved, decision='reject')
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(rejected.json()['readiness_verdict']['verdict'], 'NO_GO')
        retry = self.review(record, key='first-approval-before-veto')
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json()['readiness_verdict']['verdict'], 'NO_GO')
        self.assertEqual(retry.json()['review_context']['latest_review']['review_id'], rejected.json()['review_context']['latest_review']['review_id'])
        # An approval prepared before the veto must not silently overwrite it.
        stale = self.review(record, key='stale-prepared-approval')
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertIn('newer review', stale.json()['detail'])
        approved_again = self.review(rejected.json())
        self.assertEqual(approved_again.status_code, 200, approved_again.text)
        self.assertEqual(approved_again.json()['readiness_verdict']['verdict'], 'GO')
        event_id = record['source_event_ids'][0]
        row = self.f.store.connection.execute('SELECT payload_json FROM connector_events WHERE connector_event_id=?', (event_id,)).fetchone()
        evidence = json.loads(row['payload_json'])
        evidence['check_run']['head_sha'] = 'e' * 40
        self.f.store.connection.execute('UPDATE connector_events SET payload_json=? WHERE connector_event_id=?', (json.dumps(evidence), event_id))
        refreshed = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
        self.assertEqual(refreshed.readiness_verdict['verdict'], 'NO_GO')
        self.assertIn('outdated', ' '.join(refreshed.readiness_verdict['review_reasons']))

    def test_review_audit_is_append_only_and_atomic(self):
        record = self.seed()
        with patch.object(self.f.store, '_append_event_cursor', side_effect=RuntimeError('injected journal failure')):
            with self.assertRaises(RuntimeError):
                self.f.store.review_release_initiative(Actor(tenant_id='tenant-api', user_id='reviewer', name='Reviewer', role='Approver'), record['initiative_id'], ReleaseReviewRequest(**review_payload(record)), 'journal-failure-key')
        self.assertEqual(self.f.store._release_reviews('tenant-api', record['initiative_id']), [])
        approved = self.review(record).json()
        review_id = approved['review_context']['latest_review']['review_id']
        # The API and its worker threads share one SQLite connection. Direct
        # test SQL must hold the store lock so another thread cannot interleave
        # a statement on that connection during the trigger assertion.
        with self.f.store.lock:
            journal_row = self.f.store.connection.execute(
                'SELECT event_id, event_type FROM audit_events WHERE event_id = ?', (review_id,)
            ).fetchone()
            self.assertIsNotNone(journal_row, f'review audit event {review_id} must exist before deletion is challenged')
            self.assertEqual(journal_row['event_type'], f"RELEASE_REVIEW:{record['initiative_id']}")
            delete_trigger = self.f.store.connection.execute(
                "SELECT tbl_name, sql FROM sqlite_master WHERE type = 'trigger' AND name = 'audit_events_no_delete'"
            ).fetchone()
            self.assertIsNotNone(delete_trigger)
            self.assertEqual(delete_trigger['tbl_name'], 'audit_events')
            self.assertIn('RAISE(ABORT', delete_trigger['sql'])
            # Some bundled SQLite builds surface RAISE(ABORT) from a trigger
            # as OperationalError rather than IntegrityError. Require a
            # database rejection, then prove the review event survived it.
            with self.assertRaises(sqlite3.DatabaseError):
                self.f.store.connection.execute('DELETE FROM audit_events WHERE event_id=?', (review_id,))
            retained = self.f.store.connection.execute(
                'SELECT event_id, event_type FROM audit_events WHERE event_id = ?', (review_id,)
            ).fetchone()
            self.assertIsNotNone(retained, 'a rejected delete must leave the review audit event durable')
            self.assertEqual(retained['event_type'], f"RELEASE_REVIEW:{record['initiative_id']}")
            reviewed_release = self.f.store.get_release_initiative('tenant-api', record['initiative_id'])
            self.assertEqual(reviewed_release.readiness_verdict['verdict'], 'GO')

    def test_concurrent_review_retries_create_one_durable_event(self):
        from concurrent.futures import ThreadPoolExecutor
        record = self.seed()
        actor = Actor(tenant_id='tenant-api', user_id='parallel-reviewer', name='Reviewer', role='Approver')
        request = ReleaseReviewRequest(**review_payload(record))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.f.store.review_release_initiative(actor, record['initiative_id'], request, 'concurrent-review-key'), range(4)))
        self.assertTrue(all(item.readiness_verdict['verdict'] == 'GO' for item in results))
        self.assertEqual(len(self.f.store._release_reviews('tenant-api', record['initiative_id'])), 1)


if __name__ == '__main__':
    unittest.main()
