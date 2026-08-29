"""Domain errors for the draft-first knowledge intake workflow."""


class KnowledgeIntakeError(Exception):
    """Base error for knowledge intake domain failures."""


class DomainValidationError(KnowledgeIntakeError, ValueError):
    """Raised when domain data violates an invariant."""


class InvalidStageTransition(KnowledgeIntakeError):
    """Raised when a workflow step is executed out of order."""


class CanonicalizationError(KnowledgeIntakeError):
    """Raised when unapproved knowledge is promoted to canonical state."""
