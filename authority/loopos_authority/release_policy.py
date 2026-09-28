"""Server-owned release evidence policy. No caller claim is an approval."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

# Capture the actual local evaluator sources once at process startup. Predicate
# changes invalidate prior policy bindings even if a version bump is missed.
_EVALUATOR_DIGEST = hashlib.sha256(b''.join(
    filename.encode() + b'\0' + (Path(__file__).parent / filename).read_bytes()
    for filename in ('release_policy.py', 'models.py', 'store.py', 'postgres_store.py', 'contracts.py', 'api.py', 'config.py')
)).hexdigest()

BASELINE_LOOPS = (
    'loop-008-requirements-traceability-loop',
    'loop-023-pull-request-review-loop',
    'loop-025-ci-pipeline-loop',
    'loop-036-release-readiness-loop',
    'loop-038-deployment-validation-loop',
    'loop-040-rollback-backup-and-recovery-loop',
)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def requirements(loop_ids: list[str]) -> list[dict[str, str]]:
    return [{'requirement_id': key, 'loop_id': key, 'check_name': f'loopos:{key}'} for key in sorted(set(BASELINE_LOOPS) | set(loop_ids))]


def release_policy(
    github_app_id: int | None = None,
    workflow_ids: tuple[int, ...] = (),
    *,
    policy_epoch: int = 1,
) -> dict[str, Any]:
    if type(policy_epoch) is not int or not 0 < policy_epoch <= 9_223_372_036_854_775_807:
        raise ValueError('Release policy epoch must be a positive 64-bit integer.')
    policy = {
        'policy_id': 'loopos-release-readiness', 'version': '1.3.0',
        'policy_epoch': policy_epoch,
        'evaluator_digest': _EVALUATOR_DIGEST,
        'max_age_seconds': 86400, 'review_ttl_seconds': 86400,
        'exception_policy': 'no-waivers', 'additional_selected_loops': True,
        'review_roles': ['Approver', 'Executive'], 'require_distinct_producer': True,
        'evidence_kind': 'github-completed-success-check-run',
        'github_release_attestor_app_id': github_app_id,
        'github_release_workflow_ids': sorted(set(workflow_ids)),
        'requirements': requirements([]),
    }
    return {**policy, 'policy_digest': digest(policy)}


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _fresh(value: Any, now: datetime, max_age: int = 86400) -> bool:
    parsed = _time(value)
    return parsed is not None and -300 <= (now - parsed).total_seconds() <= max_age


def _object_json(value: Any) -> dict[str, Any] | None:
    """Decode untrusted provider JSON without allowing malformed rows to crash evaluation."""
    try:
        parsed = json.loads(value) if isinstance(value, (str, bytes, bytearray)) else None
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _positive_provider_id(value: Any) -> int | None:
    # bool is an int subclass in Python; explicitly reject it as an identity.
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value > 9_223_372_036_854_775_807:
        return None
    return value


def _latest_workflow_proof(
    event_rows: dict[str, Any], *, tenant_id: str, workspace_id: str,
    check_suite_id: int, repository_name: str, commit_sha: str,
    trusted_workflows: set[int], now: datetime,
) -> bool:
    """Require the newest signed state for an approved workflow to be successful."""
    candidates: list[tuple[tuple[Any, ...], dict[str, Any], dict[str, Any], bool]] = []
    malformed_workflow_evidence = False
    for source in event_rows.values():
        if (source.get('system') != 'github' or source.get('event_kind') != 'workflow'
                or source.get('verification_status') != 'verified_webhook'
                or source.get('tenant_id') != tenant_id or source.get('workspace_id') != workspace_id):
            continue
        payload = _object_json(source.get('payload_json'))
        if payload is None:
            malformed_workflow_evidence = True
            continue
        run = payload.get('workflow_run')
        if not isinstance(run, dict) or _positive_provider_id(run.get('check_suite_id')) != check_suite_id:
            continue
        workflow = payload.get('workflow') if isinstance(payload.get('workflow'), dict) else {}
        workflow_id = _positive_provider_id(run.get('workflow_id', workflow.get('id')))
        if workflow_id not in trusted_workflows:
            continue
        repository = payload.get('repository') if isinstance(payload.get('repository'), dict) else {}
        if repository.get('full_name') != repository_name or run.get('head_sha') != commit_sha:
            continue
        try:
            payload_matches = digest(payload) == source.get('payload_hash')
        except (TypeError, ValueError, RecursionError):
            payload_matches = False
        malformed_workflow_evidence = malformed_workflow_evidence or not payload_matches
        observed = _time(source.get('observed_at'))
        if not payload_matches or observed is None or not _fresh(source.get('observed_at'), now):
            # A matching but invalid/stale provider observation must remain the
            # latest state so it cannot be hidden by an older successful run.
            observed = observed or datetime.min.replace(tzinfo=timezone.utc)
        attempt = _positive_provider_id(run.get('run_attempt')) or 0
        state_time = (_time(run.get('updated_at')) or _time(run.get('completed_at'))
                      or _time(run.get('created_at')) or observed)
        key = (attempt, state_time, observed, str(source.get('created_at') or ''), str(source.get('connector_event_id') or ''))
        candidates.append((key, source, run, payload_matches))
    if not candidates or malformed_workflow_evidence:
        return False
    _, source, run, payload_matches = max(candidates, key=lambda item: item[0])
    return bool(
        payload_matches
        and
        _fresh(source.get('observed_at'), now)
        and _object_json(source.get('payload_json')) is not None
        and run.get('status') == 'completed'
        and run.get('conclusion') == 'success'
    )


def evaluate_release(
    initiative: Any,
    event_rows: dict[str, Any],
    now_text: str,
    latest_review: dict[str, Any] | None,
    exception_history: list[dict[str, str]] | None = None,
    observed_check_rows: dict[str, Any] | None = None,
    github_app_id: int | None = None,
    workflow_ids: tuple[int, ...] = (),
    policy_epoch: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Store adapters return sqlite3.Row or DB-API records; normalize once so
    # malformed provider payload handling is identical on SQLite and Postgres.
    event_rows = {key: dict(value) for key, value in event_rows.items()}
    observed_check_rows = {key: dict(value) for key, value in (observed_check_rows or {}).items()}
    policy = release_policy(github_app_id, workflow_ids, policy_epoch=policy_epoch)
    assurance = initiative.release_assurance
    now = _time(now_text) or datetime.now(timezone.utc)
    problems: list[str] = []
    subject = assurance.get('release_subject', {})
    if not isinstance(subject, dict) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', str(subject.get('repository', ''))) or not re.fullmatch(r'[a-f0-9]{40}', str(subject.get('commit_sha', ''))):
        problems.append('release_subject requires an exact repository and immutable commit SHA')
        subject = {}
    if any(assurance.get(key) != policy[source] for key, source in [('policy_id', 'policy_id'), ('policy_version', 'version'), ('policy_digest', 'policy_digest')]):
        problems.append('release policy binding is missing, unknown, or outdated')
    if assurance.get('release_name') != initiative.release_name:
        problems.append('release profile name does not match the recorded release')
    if assurance.get('exceptions'):
        problems.append('no-waivers policy: exception claims, including claimed closure, require a new remediated release subject and review')
    if exception_history:
        problems.append('this exact repository/commit has declared exception history; creating another record cannot erase its unresolved risk')
    trusted_workflows = set(policy['github_release_workflow_ids'])
    if policy['github_release_attestor_app_id'] is None or not trusted_workflows:
        problems.append('approved GitHub release app and workflow IDs are not configured')
    external = {item['ref_id']: item for item in assurance.get('external_refs', [])}
    gates = assurance.get('gates', [])
    artifacts = assurance.get('evidence_artifacts', [])
    required = requirements(initiative.loop_bundle_ids)
    required_loops = {item['loop_id'] for item in required}
    observed_check_rows = observed_check_rows or {}
    observed_by_name: dict[str, list[tuple[tuple[Any, ...], Any, dict[str, Any]]]] = {}
    for row in observed_check_rows.values():
        payload = _object_json(row.get('payload_json')) or {}
        check = payload.get('check_run') if isinstance(payload.get('check_run'), dict) else {}
        # Provider state time prevents an out-of-order old success from masking
        # a newer failed completion. Unknown state times remain conservative.
        observed = _time(row['observed_at']) or now
        state_time = _time(check.get('completed_at')) or _time(check.get('started_at')) or observed
        key = (state_time, observed, row['created_at'], row['connector_event_id'])
        name = check.get('name') if isinstance(check.get('name'), str) else '<invalid-check-name>'
        observed_by_name.setdefault(name, []).append((key, row, payload))
    current_checks = {name: max(entries, key=lambda entry: entry[0])[1:] for name, entries in observed_by_name.items()}
    blocking_observed_check_event_ids: list[str] = []
    for name, current in current_checks.items():
        current, payload = current
        check = payload.get('check_run') if isinstance(payload.get('check_run'), dict) else {}
        try:
            valid_digest = digest(payload) == current.get('payload_hash')
        except (TypeError, ValueError, RecursionError):
            valid_digest = False
        if not valid_digest or not _fresh(current.get('observed_at'), now) or not _fresh(check.get('completed_at'), now) or check.get('status') != 'completed' or check.get('conclusion') != 'success':
            problems.append(f'observed check {name}: current provider state is adverse, pending, stale, or invalid')
            event_id = current.get('connector_event_id')
            if isinstance(event_id, str) and event_id not in blocking_observed_check_event_ids:
                blocking_observed_check_event_ids.append(event_id)
    if any(gate.get('loop_id') not in required_loops for gate in gates):
        problems.append('submitted gates must belong to protected baseline or selected-loop requirements')
    for requirement in required:
        loop_id, check_name = requirement['loop_id'], requirement['check_name']
        matching = [gate for gate in gates if gate.get('loop_id') == loop_id]
        if len(matching) != 1:
            problems.append(f'{loop_id}: exactly one protected gate is required')
            continue
        gate = matching[0]
        if gate.get('status') != 'passed':
            problems.append(f'{loop_id}: gate has not passed')
        if gate.get('required_evidence') != [check_name]:
            problems.append(f'{loop_id}: required evidence must exactly match the protected check; unsupported additional declarations cannot pass')
        candidates = [artifact for artifact in artifacts if artifact.get('gate_id') == gate['gate_id'] and artifact.get('loop_id') == loop_id and artifact.get('label') == check_name]
        if len(candidates) != 1:
            problems.append(f'{loop_id}: exactly one bound required artifact is required')
            continue
        artifact = candidates[0]
        event_id = artifact.get('source_ref')
        event = event_rows.get(event_id)
        ref = external.get(event_id)
        current = current_checks.get(check_name)
        if current is None or current[0].get('connector_event_id') != event_id:
            problems.append(f'{loop_id}: selected evidence is not the latest observed provider check state')
        if artifact.get('required') is not True or artifact.get('freshness') != 'fresh' or not _fresh(artifact.get('observed_at'), now):
            problems.append(f'{loop_id}: required artifact is missing, stale, or invalid')
        if event is None or not isinstance(ref, dict) or event_id not in initiative.source_event_ids:
            problems.append(f'{loop_id}: artifact must reference a linked verified connector event')
            continue
        if event['verification_status'] != 'verified_webhook' or event['system'] != 'github' or event['event_kind'] != 'check':
            problems.append(f'{loop_id}: a verified GitHub check event is required')
        if ref.get('evidence_hash') != event['payload_hash'] or ref.get('system') != 'github' or ref.get('object_type') != 'check':
            problems.append(f'{loop_id}: source hash or source type does not match observed evidence')
        if not _fresh(event['observed_at'], now) or not _fresh(ref.get('observed_at'), now):
            problems.append(f'{loop_id}: source evidence is stale or has an invalid timestamp')
        payload = _object_json(event.get('payload_json')) or {}
        try:
            valid_event_digest = digest(payload) == event.get('payload_hash')
        except (TypeError, ValueError, RecursionError):
            valid_event_digest = False
        if not valid_event_digest:
            problems.append(f'{loop_id}: stored event content does not match its digest')
        check = payload.get('check_run') if isinstance(payload.get('check_run'), dict) else {}
        repository = payload.get('repository') if isinstance(payload.get('repository'), dict) else {}
        if repository.get('full_name') != subject.get('repository') or check.get('head_sha') != subject.get('commit_sha'):
            problems.append(f'{loop_id}: check evidence belongs to a different release subject')
        if check.get('name') != check_name or check.get('status') != 'completed' or check.get('conclusion') != 'success' or not _fresh(check.get('completed_at'), now):
            problems.append(f'{loop_id}: required check has no current successful completion')
        app = check.get('app') if isinstance(check.get('app'), dict) else {}
        app_identity = _positive_provider_id(app.get('id'))
        if app_identity != policy['github_release_attestor_app_id']:
            problems.append(f'{loop_id}: check publisher is not the configured GitHub App')
        check_suite = check.get('check_suite') if isinstance(check.get('check_suite'), dict) else {}
        check_suite_id = _positive_provider_id(check_suite.get('id'))
        accepted_workflow = bool(check_suite_id and _latest_workflow_proof(
            event_rows, tenant_id=str(event.get('tenant_id')), workspace_id=str(event.get('workspace_id')),
            check_suite_id=check_suite_id, repository_name=str(subject.get('repository', '')),
            commit_sha=str(subject.get('commit_sha', '')), trusted_workflows=trusted_workflows, now=now,
        ))
        if not accepted_workflow:
            problems.append(f'{loop_id}: no successful workflow evidence from an approved workflow matches this check suite and commit')
        decisions = [item for item in assurance.get('decisions', []) if item.get('gate_id') == gate['gate_id']]
        if len(decisions) != 1 or event_id not in decisions[0].get('source_ref_ids', []):
            problems.append(f'{loop_id}: current gate claim is not bound to its observed evidence')
        elif not _fresh(decisions[0].get('decided_at'), now):
            problems.append(f'{loop_id}: current gate claim timestamp is invalid or stale')
    # Additional submitted gates may strengthen, never weaken, the baseline.
    if any(gate.get('status') != 'passed' for gate in gates):
        problems.append('every submitted release gate must pass')
    for artifact in artifacts:
        if artifact.get('required'):
            if artifact.get('freshness') != 'fresh' or not _fresh(artifact.get('observed_at'), now):
                problems.append(f"required artifact {artifact.get('artifact_id')} is not current")
            if artifact.get('loop_id') not in required_loops or artifact.get('label') != f"loopos:{artifact.get('loop_id')}":
                problems.append(f"required artifact {artifact.get('artifact_id')} is not an observed protected evidence slot")
            if not any(gate['gate_id'] == artifact.get('gate_id') and gate['loop_id'] == artifact.get('loop_id') for gate in gates):
                problems.append(f"required artifact {artifact.get('artifact_id')} has an inconsistent gate/loop binding")
    source_records = [{key: row[key] for key in ('connector_event_id', 'tenant_id', 'workspace_id', 'system', 'event_kind', 'payload_hash', 'payload_json', 'verification_status', 'observed_at', 'delivery_id')} for _, row in sorted(event_rows.items())]
    observed_records = [{key: row[key] for key in ('connector_event_id', 'workspace_id', 'payload_hash', 'payload_json', 'observed_at', 'created_at')} for _, row in sorted(observed_check_rows.items())]
    evidence_digest = digest({'events': source_records, 'observed_checks': observed_records, 'required': required, 'artifacts': artifacts, 'external_refs': assurance.get('external_refs', []), 'exception_history': exception_history or []})
    subject_digest = digest({
        'tenant_id': initiative.tenant_id, 'workspace_id': initiative.workspace_id,
        'initiative_id': initiative.initiative_id, 'created_by': initiative.created_by,
        'release_name': initiative.release_name, 'workflow_type': initiative.workflow_type,
        'title': initiative.title, 'description': initiative.description, 'business_outcome': initiative.business_outcome,
        'maturity': initiative.maturity, 'status': initiative.status, 'created_at': initiative.created_at,
        'risk_tier': initiative.risk_tier, 'loop_bundle_ids': initiative.loop_bundle_ids,
        'source_event_ids': initiative.source_event_ids, 'release_assurance': assurance,
    })
    evidence_problems = list(dict.fromkeys(problems))
    review_problems: list[str] = []
    if latest_review is None:
        review_problems.append('an authenticated independent release review is required')
    else:
        if latest_review.get('subject_digest') != subject_digest or latest_review.get('policy_digest') != policy['policy_digest'] or latest_review.get('evidence_digest') != evidence_digest:
            review_problems.append('authenticated review binding is outdated')
        if latest_review.get('reviewer_id') == initiative.created_by or latest_review.get('reviewer_role') not in policy['review_roles']:
            review_problems.append('authenticated review does not satisfy separation of duties')
        if not _fresh(latest_review.get('reviewed_at'), now, policy['review_ttl_seconds']):
            review_problems.append('authenticated review has expired or has an invalid timestamp')
        if latest_review.get('decision') != 'approve':
            problems.append('the current authenticated review rejects release readiness')
    context = {
        'subject_digest': subject_digest, 'policy_digest': policy['policy_digest'], 'evidence_digest': evidence_digest,
        'policy_epoch': policy['policy_epoch'],
        'reviewable': not evidence_problems, 'blocking_reasons': evidence_problems, 'latest_review': latest_review,
        'observed_check_event_ids': sorted(observed_check_rows),
        'blocking_observed_check_event_ids': sorted(blocking_observed_check_event_ids),
    }
    verdict = {
        'verdict': 'NO_GO' if problems else 'REVIEW_REQUIRED' if review_problems else 'GO',
        'evaluated_at': now_text, 'policy_id': policy['policy_id'], 'policy_version': policy['version'], 'policy_digest': policy['policy_digest'],
        'policy_epoch': policy['policy_epoch'],
        'subject_digest': subject_digest, 'evidence_digest': evidence_digest,
        'policy': 'Protected baseline and selected-loop checks, exact release subject, fresh verified evidence, no exceptions, and independent authenticated review are required; readiness never authorizes deployment.',
        'gate_status_counts': {status: sum(gate.get('status') == status for gate in gates) for status in sorted({gate.get('status', 'missing') for gate in gates})},
        'failing_reasons': list(dict.fromkeys(problems)), 'review_reasons': review_problems,
    }
    return verdict, context
