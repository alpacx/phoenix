"""Provider-independent selection and monotonic rotation deadline."""
import secrets

RESTRICTED = frozenset('CN RU BY TR IQ AE OM IN IR EG TM KP UG MM SA VE'.split())


def choose_country(countries, fixed='', previous='', exclude=False, choice=secrets.choice):
    eligible = sorted(set(countries) - (RESTRICTED if exclude else set()))
    if fixed:
        if fixed not in eligible:
            raise ValueError('country_unavailable_or_excluded')
        return fixed
    if len(eligible) > 1 and previous in eligible:
        eligible.remove(previous)
    if not eligible:
        raise ValueError('no_eligible_countries')
    return choice(eligible)


class Rotation:
    def __init__(self, clock):
        self.clock = clock
        self.deadline = None

    def connected(self, enabled, interval):
        if type(enabled) is not bool or type(interval) is not int or not 30 <= interval <= 86400:
            raise ValueError('invalid_rotation')
        self.deadline = self.clock() + interval if enabled else None

    def disconnected(self):
        self.deadline = None

    def remaining(self):
        import math
        return 0 if self.deadline is None else max(0, math.ceil(self.deadline - self.clock()))

    def due(self):
        return self.deadline is not None and self.clock() >= self.deadline
