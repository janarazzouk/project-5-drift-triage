class WorkerError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class QueueReadError(WorkerError):
    pass


class InvalidJobError(WorkerError):
    pass


class UnknownJobTypeError(WorkerError):
    pass


class ToolExecutionError(WorkerError):
    pass


class ExternalServiceError(WorkerError):
    pass