from __future__ import annotations


def build_formula(
    *,
    outcome: str,
    main_var: str,
    interaction_var: str | None,
    controls: list[str] | None,
    fixed_effects: list[str] | None,
) -> str:
    rhs_terms: list[str] = []
    controls = controls or []
    fixed_effects = fixed_effects or []

    if interaction_var:
        rhs_terms.append(f"{main_var} * {interaction_var}")
        excluded_controls = {main_var, interaction_var}
    else:
        rhs_terms.append(main_var)
        excluded_controls = {main_var}

    for control in controls:
        if control not in excluded_controls and control not in rhs_terms:
            rhs_terms.append(control)

    for fixed_effect in fixed_effects:
        rhs_terms.append(f"C({fixed_effect})")

    return f"{outcome} ~ " + " + ".join(rhs_terms)
