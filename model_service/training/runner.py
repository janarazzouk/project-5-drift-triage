import joblib
import pandas as pd

from training.artifacts import (
    build_environment,
    build_reference_stats,
    build_replay_fixture,
    build_runtime_config_base,
    build_schema,
    save_model_card,
)
from training.config import TrainingConfig
from training.data import (
    get_feature_groups,
    load_bank_marketing_data,
    make_train_val_test_split,
)
from training.io_utils import archive_existing_artifacts, save_json, utc_now
from training.metrics import (
    choose_highest_threshold_for_recall,
    evaluate,
    prefix_metrics,
)
from training.mlflow_registry import log_and_register_model, log_extra_artifacts_to_run
from training.pipeline import build_pipeline, predict_positive_probability


def run_training(config: TrainingConfig) -> dict:
    artifact_dir = config.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    archived_dir = archive_existing_artifacts(
        artifact_dir,
        enabled=config.archive_existing_artifacts,
    )

    X, y = load_bank_marketing_data(
        config.training_data_path,
        target_column=config.target_column,
    )
    numeric_features, categorical_features = get_feature_groups(X)

    splits = make_train_val_test_split(
        X,
        y,
        random_state=config.random_state,
    )

    pipeline = build_pipeline(
        numeric_features,
        categorical_features,
        random_state=config.random_state,
    )
    pipeline.fit(splits.X_train, splits.y_train)

    train_probabilities = predict_positive_probability(pipeline, splits.X_train)
    val_probabilities = predict_positive_probability(pipeline, splits.X_val)
    test_probabilities = predict_positive_probability(pipeline, splits.X_test)

    selected_threshold = choose_highest_threshold_for_recall(
        splits.y_val,
        val_probabilities,
        min_recall=config.min_recall,
    )

    train_metrics = evaluate(
        splits.y_train,
        train_probabilities,
        threshold=selected_threshold,
    )
    val_metrics = evaluate(
        splits.y_val,
        val_probabilities,
        threshold=selected_threshold,
    )
    test_metrics = evaluate(
        splits.y_test,
        test_probabilities,
        threshold=selected_threshold,
    )

    metrics = {
        **prefix_metrics("train", train_metrics),
        **prefix_metrics("val", val_metrics),
        **prefix_metrics("test", test_metrics),
        "accuracy": test_metrics["accuracy"],
        "auc": test_metrics["auc"],
        "f1": test_metrics["f1"],
        "precision": test_metrics["precision"],
        "recall": test_metrics["recall"],
        "selected_threshold": selected_threshold,
        "min_required_recall": config.min_recall,
    }

    runtime_config_base = build_runtime_config_base(
        selected_threshold=selected_threshold,
        artifact_dir=artifact_dir,
        data_path=config.training_data_path,
        target_column=config.target_column,
        random_state=config.random_state,
        train_rows=len(splits.X_train),
        val_rows=len(splits.X_val),
        test_rows=len(splits.X_test),
    )

    test_predictions = (test_probabilities >= selected_threshold).astype(int)

    joblib.dump(pipeline, artifact_dir / "model_pipeline.joblib")
    save_json(
        artifact_dir / "schema.json",
        build_schema(
            X,
            target_column=config.target_column,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
        ),
    )
    save_json(
        artifact_dir / "reference_stats.json",
        build_reference_stats(
            X_reference=splits.X_train,
            y_reference=splits.y_train,
            reference_probabilities=train_probabilities,
            reference_predictions=(train_probabilities >= selected_threshold).astype(int),
            numeric_features=numeric_features,
            categorical_features=categorical_features,
        ),
    )
    save_json(
        artifact_dir / "replay_fixture.json",
        build_replay_fixture(
            X_test=splits.X_test,
            y_test=splits.y_test,
            probabilities=test_probabilities,
            threshold=selected_threshold,
            random_state=config.random_state,
        ),
    )
    save_json(artifact_dir / "metrics.json", metrics)
    save_json(artifact_dir / "environment.json", build_environment())
    save_json(artifact_dir / "runtime_config.json", runtime_config_base)

    mlflow_run_id, model_version, model_uri = log_and_register_model(
        config=config,
        model=pipeline,
        artifact_dir=artifact_dir,
        metrics=metrics,
        selected_threshold=selected_threshold,
        runtime_config_base=runtime_config_base,
        X_example=splits.X_train,
    )

    runtime_config = {
        **runtime_config_base,
        "registered_model_name": config.mlflow_model_name,
        "mlflow_run_id": mlflow_run_id,
        "model_version": model_version,
        "model_artifact_path": "model",
        "mlflow_model_uri": model_uri,
    }
    save_json(artifact_dir / "runtime_config.json", runtime_config)

    save_model_card(
        artifact_dir / "model_card.md",
        metrics=metrics,
        selected_threshold=selected_threshold,
        data_path=config.training_data_path,
        artifact_dir=artifact_dir,
        target_column=config.target_column,
        min_recall=config.min_recall,
        mlflow_model_name=config.mlflow_model_name,
        model_version=model_version,
        mlflow_run_id=mlflow_run_id,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    summary = {
        "completed": True,
        "created_at": utc_now(),
        "artifact_dir": str(artifact_dir),
        "archived_previous_artifacts_dir": str(archived_dir) if archived_dir else None,
        "registered_model_name": config.mlflow_model_name,
        "model_version": model_version,
        "mlflow_run_id": mlflow_run_id,
        "mlflow_model_uri": model_uri,
        "selected_threshold": selected_threshold,
        "test_metrics": test_metrics,
        "test_prediction_class_distribution": {
            str(key): int(value)
            for key, value in pd.Series(test_predictions)
            .value_counts()
            .sort_index()
            .to_dict()
            .items()
        },
    }
    save_json(artifact_dir / "training_summary.json", summary)

    log_extra_artifacts_to_run(
        mlflow_tracking_uri=config.mlflow_tracking_uri,
        mlflow_run_id=mlflow_run_id,
        artifact_paths=[
            artifact_dir / "runtime_config.json",
            artifact_dir / "model_card.md",
            artifact_dir / "training_summary.json",
        ],
    )

    _print_training_summary(
        artifact_dir=artifact_dir,
        archived_dir=archived_dir,
        model_name=config.mlflow_model_name,
        model_version=model_version,
        mlflow_run_id=mlflow_run_id,
        selected_threshold=selected_threshold,
        test_metrics=test_metrics,
    )

    return summary


def _print_training_summary(
    *,
    artifact_dir,
    archived_dir,
    model_name: str,
    model_version: str,
    mlflow_run_id: str,
    selected_threshold: float,
    test_metrics: dict[str, float],
) -> None:
    print("Training completed successfully.")
    print(f"Artifacts saved to: {artifact_dir}")

    if archived_dir:
        print(f"Previous artifacts archived to: {archived_dir}")

    print(f"MLflow registered model: {model_name}")
    print(f"MLflow model version: {model_version}")
    print(f"MLflow run id: {mlflow_run_id}")
    print(f"Selected threshold: {selected_threshold:.6f}")
    print(
        "Test metrics: "
        f"accuracy={test_metrics['accuracy']:.4f}, "
        f"precision={test_metrics['precision']:.4f}, "
        f"recall={test_metrics['recall']:.4f}, "
        f"f1={test_metrics['f1']:.4f}, "
        f"auc={test_metrics['auc']:.4f}"
    )