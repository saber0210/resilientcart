def can_reserve(available: int, requested: int) -> bool:
    return requested > 0 and available >= requested
