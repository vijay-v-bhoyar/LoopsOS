SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '60s';

-- The authority service owns one active release evaluator epoch per database.
-- The service role is server-only; browser roles receive no access.
CREATE TABLE IF NOT EXISTS release_policy_control (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  epoch BIGINT NOT NULL CHECK (epoch > 0),
  policy_version TEXT NOT NULL,
  policy_digest TEXT NOT NULL CHECK (policy_digest ~ '^[a-f0-9]{64}$'),
  evaluator_digest TEXT NOT NULL CHECK (evaluator_digest ~ '^[a-f0-9]{64}$'),
  activated_at TEXT NOT NULL
);

ALTER TABLE release_policy_control ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.loopos_release_policy_epoch_guard()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF TG_OP = 'DELETE' OR TG_OP = 'TRUNCATE' THEN
    RAISE EXCEPTION 'release policy epoch control cannot be removed';
  END IF;
  IF TG_OP = 'UPDATE' AND (
    NEW.epoch < OLD.epoch OR
    (NEW.epoch = OLD.epoch AND (
      NEW.policy_version IS DISTINCT FROM OLD.policy_version OR
      NEW.policy_digest IS DISTINCT FROM OLD.policy_digest OR
      NEW.evaluator_digest IS DISTINCT FROM OLD.evaluator_digest OR
      NEW.activated_at IS DISTINCT FROM OLD.activated_at
    ))
  ) THEN
    RAISE EXCEPTION 'release policy epoch is monotonic';
  END IF;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.loopos_release_policy_epoch_guard() FROM PUBLIC;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid = 'public.release_policy_control'::regclass
      AND tgname = 'release_policy_control_monotonic'
      AND NOT tgisinternal
  ) THEN
    EXECUTE 'CREATE TRIGGER release_policy_control_monotonic BEFORE UPDATE ON public.release_policy_control FOR EACH ROW EXECUTE FUNCTION public.loopos_release_policy_epoch_guard()';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid = 'public.release_policy_control'::regclass
      AND tgname = 'release_policy_control_no_delete'
      AND NOT tgisinternal
  ) THEN
    EXECUTE 'CREATE TRIGGER release_policy_control_no_delete BEFORE DELETE ON public.release_policy_control FOR EACH ROW EXECUTE FUNCTION public.loopos_release_policy_epoch_guard()';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid = 'public.release_policy_control'::regclass
      AND tgname = 'release_policy_control_no_truncate'
      AND NOT tgisinternal
  ) THEN
    EXECUTE 'CREATE TRIGGER release_policy_control_no_truncate BEFORE TRUNCATE ON public.release_policy_control FOR EACH STATEMENT EXECUTE FUNCTION public.loopos_release_policy_epoch_guard()';
  END IF;
END;
$$;

DO $$
DECLARE role_name text;
BEGIN
  FOR role_name IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated') LOOP
    EXECUTE format('REVOKE ALL ON release_policy_control FROM %I', role_name);
    EXECUTE format('REVOKE ALL ON FUNCTION public.loopos_release_policy_epoch_guard() FROM %I', role_name);
  END LOOP;
END;
$$;
