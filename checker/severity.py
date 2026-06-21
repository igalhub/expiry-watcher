def compute_severity(days_remaining: int) -> str:
    if days_remaining <= 0:
        return "expired"
    if days_remaining <= 7:
        return "critical"
    if days_remaining <= 30:
        return "warning"
    return "healthy"
