from app.schemas.job import WorkerJobEnvelope


class JobService:
    def describe_job(
        self,
        job: WorkerJobEnvelope,
    ) -> str:
        return (
            f"Job {job.job_id} of type {job.job_type} "
            f"for investigation {job.investigation_id}."
        )