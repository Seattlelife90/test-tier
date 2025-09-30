VANITY_RULES = {
    # AU example: 99.63 -> 99.95
    "AU": {"suffix": 0.95, "nines": True},  # xx9.95 closest
    # CA example: 89.36 -> 89.99
    "CA": {"suffix": 0.99, "nines": True},  # xx9.99 closest
    # NZ: match AU convention xx9.95
    "NZ": {"suffix": 0.95, "nines": True},
}
