"""Hard constraints (minimums) management."""


class ConstraintManager:
    """Manages hard constraints (minimum stat requirements)."""

    def __init__(self):
        """Initialize constraint manager."""
        self.min_constraints: dict[str, int] = {}

    def add_min_constraint(self, stat_name: str, value: int) -> None:
        """
        Add a minimum constraint for a stat.

        Args:
            stat_name: Name of the stat
            value: Minimum required value
        """
        self.min_constraints[stat_name] = value

    def set_min_constraints(self, constraints: dict[str, int]) -> None:
        """
        Set multiple minimum constraints at once.

        Args:
            constraints: Dictionary mapping stat names to minimum values
        """
        self.min_constraints.update(constraints)

    def violates_hard_constraints(self, stats: dict[str, int]) -> list[str]:
        """
        Check if stats violate any hard constraints.

        Args:
            stats: Dictionary of stat names to values

        Returns:
            List of violation messages (empty if no violations)
        """
        violations = []
        for stat, min_val in self.min_constraints.items():
            stat_value = stats.get(stat, 0)
            if stat_value < min_val:
                violations.append(
                    f"{stat} is {stat_value}, need at least {min_val}"
                )
        return violations
