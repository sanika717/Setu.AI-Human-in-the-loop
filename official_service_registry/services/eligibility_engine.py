from typing import Any

from ..models.schemas import EligibilityRule, EligibilityRuleResult

_OPERATORS = {
    "gte": lambda actual, expected: actual >= expected,
    "lte": lambda actual, expected: actual <= expected,
    "gt": lambda actual, expected: actual > expected,
    "lt": lambda actual, expected: actual < expected,
    "eq": lambda actual, expected: actual == expected,
    "ne": lambda actual, expected: actual != expected,
    "in": lambda actual, expected: actual in expected,
    "exists": lambda actual, expected: (actual is not None) == bool(expected),
}


class EligibilityEngine:
    """Evaluates a service's `eligibility_rules` against an applicant context.

    This never branches on a service name or category - every rule is pure
    data (`{field, operator, value, message}`), so a new service with an
    entirely different eligibility policy (age gate, active-account flag,
    active-policy flag, etc.) never requires touching this code, only the
    registry entry.
    """

    def evaluate(
        self, rules: list[EligibilityRule], applicant_context: dict[str, Any]
    ) -> tuple[bool | None, list[EligibilityRuleResult]]:
        if not rules:
            return None, []

        results: list[EligibilityRuleResult] = []
        any_unknown = False

        for rule in rules:
            if rule.field not in applicant_context or applicant_context[rule.field] is None:
                results.append(
                    EligibilityRuleResult(
                        field=rule.field,
                        operator=rule.operator,
                        passed=None,
                        message=f"'{rule.field}' was not supplied; could not evaluate: {rule.message}",
                    )
                )
                any_unknown = True
                continue

            comparator = _OPERATORS[rule.operator]
            try:
                passed = bool(comparator(applicant_context[rule.field], rule.value))
            except TypeError:
                # Incomparable types (e.g. comparing a string to an int) -
                # treat as "could not evaluate" rather than raising, so one
                # malformed context field never 500s the whole request.
                results.append(
                    EligibilityRuleResult(
                        field=rule.field,
                        operator=rule.operator,
                        passed=None,
                        message=f"'{rule.field}' has an incompatible type for this rule: {rule.message}",
                    )
                )
                any_unknown = True
                continue

            results.append(
                EligibilityRuleResult(
                    field=rule.field,
                    operator=rule.operator,
                    passed=passed,
                    message=rule.message,
                )
            )

        if any((r.passed is False) for r in results):
            return False, results
        if any_unknown:
            return None, results
        return True, results
