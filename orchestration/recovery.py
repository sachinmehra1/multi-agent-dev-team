"""Bounded, call-level recovery. Never replay an agent workflow."""
import random
import time
import httpx


class CircuitOpen(RuntimeError):
    pass


class TransientToolError(RuntimeError):
    pass


def transient(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {408,409,429,500,502,503,504}
    return isinstance(exc, (httpx.TransportError, TimeoutError, ConnectionError, OSError, TransientToolError))


class CircuitBreaker:
    def __init__(self, cooldown=30, clock=time.monotonic, event=lambda *a,**k:None):
        if cooldown <= 0: raise ValueError('Circuit cooldown must be positive')
        self.cooldown, self.clock, self.event = cooldown, clock, event
        self.state, self.failures, self.opened_at = 'closed', 0, None

    def transition(self, state):
        previous, self.state = self.state, state
        if state == 'open': self.opened_at = self.clock()
        self.event('circuit_transition', level='WARNING', previous=previous, state=state)

    def before(self):
        if self.state == 'open':
            if self.clock() - self.opened_at < self.cooldown:
                raise CircuitOpen('Circuit is open; call was not sent')
            self.transition('half_open')

    def success(self):
        self.failures = 0
        if self.state != 'closed': self.transition('closed')

    def failure(self):
        self.failures += 1
        if self.state == 'half_open' or self.failures >= 3:
            self.transition('open')


class CallPolicy:
    def __init__(self, retries=3, base_delay=.25, cooldown=30, *, clock=time.monotonic,
                 sleep=time.sleep, jitter=random.uniform, event=lambda *a,**k:None):
        if not 0 <= retries <= 3: raise ValueError('At most three retries are allowed')
        if base_delay < 0: raise ValueError('Backoff must be nonnegative')
        self.retries, self.base_delay = retries, base_delay
        self.sleep, self.jitter, self.event = sleep, jitter, event
        self.breaker = CircuitBreaker(cooldown, clock, event)

    def call(self, operation):
        for attempt in range(self.retries + 1):
            self.breaker.before()
            self.event('call_attempt', attempt=attempt+1, retry_number=attempt)
            try:
                result = operation()
            except Exception as exc:
                if not transient(exc): raise
                self.breaker.failure()
                self.event('call_failed', error_type=type(exc).__name__, attempt=attempt+1)
                if self.breaker.state == 'open' or attempt == self.retries: raise
                delay = self.base_delay * 2**attempt + self.jitter(0,self.base_delay)
                self.event('retry_scheduled', retry_number=attempt+1, delay_seconds=delay)
                self.sleep(delay)
            else:
                self.breaker.success()
                return result


class PromptCache:
    def __init__(self, ttl=300, clock=time.monotonic):
        if ttl < 0: raise ValueError('Cache TTL must be nonnegative')
        self.ttl, self.clock, self.entries = ttl, clock, {}

    def get(self, key):
        entry = self.entries.get(key)
        if entry is None: return None
        if self.clock() >= entry[0]:
            del self.entries[key]
            return None
        return entry[1]

    def put(self, key, value):
        if self.ttl: self.entries[key] = (self.clock()+self.ttl, value)
