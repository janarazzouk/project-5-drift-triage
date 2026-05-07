from pydantic import BaseModel


class RetrainResult(BaseModel):
    completed: bool
    exit_code: int
    stdout_tail: str
    stderr_tail: str