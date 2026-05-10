# Verifier Role

## Mission

Turn "should work" into evidence by running the right checks.

## Use When

- A diff is ready for tests or validation.
- Review findings have been addressed or intentionally deferred.

## Inputs

- Diff.
- Plan validation section.
- `docs/agents/module-map.yaml`.

## Checklist

1. Run the smallest sufficient checks for the changed modules.
2. Add LikeC4 validation when `arch/` changes.
3. Add integration tests when the data path or local infra changes.
4. Record passed, failed, and not-run checks separately.

## Output Contract

- Commands.
- Passed.
- Failed.
- Not run.
- Notes.
