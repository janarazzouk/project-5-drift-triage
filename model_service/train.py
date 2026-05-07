from training.config import load_training_config
from training.runner import run_training


def main() -> None:
    config = load_training_config()
    run_training(config)


if __name__ == "__main__":
    main()