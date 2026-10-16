"""Authorization helpers shared by the services that read DA data.

Lives here, next to the models it reads, so agent-platform and
connector-service resolve DA grants with one copy of the rule rather
than two that drift.
"""
