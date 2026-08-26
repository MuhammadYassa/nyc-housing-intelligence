from enum import StrEnum

class ImportRunStatus(StrEnum):
    STARTED = "STARTED"
    EXTRACTED = "EXTRACTED"
    STAGED = "STAGED"
    TRANSFORMED = "TRANSFORMED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"