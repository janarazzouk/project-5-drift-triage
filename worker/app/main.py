from app.core.deps import get_consumer, initialize_resources
from app.core.logging import configure_logging, get_logger


logger = get_logger(__name__)


def main() -> None:
    configure_logging()
    initialize_resources()

    consumer = get_consumer()

    logger.info("Starting drift triage worker.")
    consumer.run_forever()


if __name__ == "__main__":
    main()