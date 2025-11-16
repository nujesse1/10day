"""
Custom Exceptions - Application-specific error types
"""


class HabitEnforcerException(Exception):
    """Base exception for all habit enforcer errors"""
    pass


class HabitNotFoundError(HabitEnforcerException):
    """Raised when a habit cannot be found"""
    pass


class HabitAlreadyExistsError(HabitEnforcerException):
    """Raised when attempting to create a duplicate habit"""
    pass


class InvalidHabitDataError(HabitEnforcerException):
    """Raised when habit data validation fails"""
    pass


class ProofVerificationError(HabitEnforcerException):
    """Raised when proof verification fails"""
    pass


class InvalidProofError(HabitEnforcerException):
    """Raised when proof is invalid or missing"""
    pass


class SchedulerError(HabitEnforcerException):
    """Raised when scheduler operations fail"""
    pass


class DatabaseError(HabitEnforcerException):
    """Raised when database operations fail"""
    pass


class ExternalServiceError(HabitEnforcerException):
    """Raised when external services (Twilio, OpenAI, etc.) fail"""
    pass


class PunishmentError(HabitEnforcerException):
    """Raised when punishment assignment or execution fails"""
    pass


class CryptoPunishmentError(PunishmentError):
    """Raised when crypto punishment fails"""
    pass
