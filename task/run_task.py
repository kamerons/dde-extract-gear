"""
Subprocess entry point for one unit of work (training run, evaluation task, or recommendation task).
Invoked as: python -m task.run_task <type> '<json_payload>'
Prints one JSON line to stdout for training (result/suspended/error); evaluation and recommendation write status to Redis only.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import redis

from task.config import Config
from task.redis_updates import update_task_progress, update_task_status
from task.processors.box_detector_processor import BoxDetectorProcessor
from task.processors.digit_detector_processor import DigitDetectorProcessor
from task.processors.icon_type_detector_processor import IconTypeDetectorProcessor
from task.processors.recommendation_processor import RecommendationProcessor
from task.processors.evaluation_processor import (
    run_evaluate as eval_run_evaluate,
    run_model_evaluation_combined as eval_run_model_evaluation_combined,
    run_preview as eval_run_preview,
)
from shared.recommendation_engine import TaskCancelledError

LATEST_PREVIEW_KEY = "extract:training:latest_preview"
PREVIEW_TTL = 3600
EVALUATION_QUEUE_NAME = "evaluation_tasks"
CURRENT_TASK_EXPIRY = 3600
QUEUE_NAME = "recommendation_tasks"
CURRENT_TASK_KEY = "recommendation_current_task_id"

_log_level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("PIL").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _run_training(
    redis_client: redis.Redis,
    config: Config,
    task_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Run one training process() call. Returns result dict (suspended, completed, or error)."""
    task_id = task_data["task_id"]
    model_type = task_data.get("model_type", "box_detector")
    resume_from_existing = task_data.get("resume_from_existing", False)
    if isinstance(resume_from_existing, str):
        resume_from_existing = resume_from_existing.lower() == "true"
    resume_from_epoch = task_data.get("resume_from_epoch")
    training_epochs = task_data.get("training_epochs")
    if training_epochs is not None:
        training_epochs = max(1, int(training_epochs))
    else:
        training_epochs = config.TRAINING_EPOCHS
    initial_learning_rate = task_data.get("initial_learning_rate")
    if initial_learning_rate is not None:
        initial_learning_rate = float(initial_learning_rate)
    else:
        initial_learning_rate = config.INITIAL_LEARNING_RATE

    if model_type == "icon_type":
        training_epochs_icon = task_data.get("training_epochs")
        if training_epochs_icon is not None:
            training_epochs_icon = max(1, int(training_epochs_icon))
        else:
            training_epochs_icon = config.ICON_TYPE_DETECTION_TRAINING_EPOCHS
        initial_lr_icon = task_data.get("initial_learning_rate")
        if initial_lr_icon is not None:
            initial_lr_icon = float(initial_lr_icon)
        else:
            initial_lr_icon = config.ICON_TYPE_DETECTION_INITIAL_LEARNING_RATE
        icon_processor = IconTypeDetectorProcessor(
            data_dir=config.DATA_DIR,
            model_path=config.ICON_TYPE_DETECTION_MODEL_PATH,
            test_ratio=config.ICON_TYPE_DETECTION_TEST_RATIO,
            epochs=training_epochs_icon,
            initial_learning_rate=initial_lr_icon,
        )

        def progress_callback_icon(epoch: int, total_epochs: int, metrics: Dict) -> None:
            update_task_progress(
                redis_client, task_id, evaluated=epoch, total_planned=total_epochs, partial_results=metrics
            )
            redis_client.setex(f"task:{task_id}:eval", 3600, json.dumps(metrics))

        def check_cancelled_icon() -> bool:
            return redis_client.get(f"task:{task_id}:cancelled") == "1"

        try:
            results = icon_processor.process(
                task_id=task_id,
                progress_callback=progress_callback_icon,
                check_cancelled=check_cancelled_icon,
            )
            return results
        except TaskCancelledError:
            raise
        except Exception as e:
            return {"error": "training_failed", "message": str(e)}

    if model_type == "digit_detector":
        training_epochs_digit = task_data.get("training_epochs")
        if training_epochs_digit is not None:
            training_epochs_digit = max(1, int(training_epochs_digit))
        else:
            training_epochs_digit = config.DIGIT_DETECTION_TRAINING_EPOCHS
        initial_lr_digit = task_data.get("initial_learning_rate")
        if initial_lr_digit is not None:
            initial_lr_digit = float(initial_lr_digit)
        else:
            initial_lr_digit = config.DIGIT_DETECTION_INITIAL_LEARNING_RATE
        digit_processor = DigitDetectorProcessor(
            data_dir=config.DATA_DIR,
            model_path=config.DIGIT_DETECTION_MODEL_PATH,
            test_ratio=config.DIGIT_DETECTION_TEST_RATIO,
            epochs=training_epochs_digit,
            initial_learning_rate=initial_lr_digit,
        )

        def progress_callback_digit(epoch: int, total_epochs: int, metrics: Dict) -> None:
            update_task_progress(
                redis_client, task_id, evaluated=epoch, total_planned=total_epochs, partial_results=metrics
            )
            redis_client.setex(f"task:{task_id}:eval", 3600, json.dumps(metrics))

        def check_cancelled_digit() -> bool:
            return redis_client.get(f"task:{task_id}:cancelled") == "1"

        try:
            results = digit_processor.process(
                task_id=task_id,
                progress_callback=progress_callback_digit,
                check_cancelled=check_cancelled_digit,
            )
            return results
        except TaskCancelledError:
            raise
        except Exception as e:
            return {"error": "training_failed", "message": str(e)}

    if model_type != "box_detector":
        return {"error": "unknown_model", "message": f"Unknown model_type: {model_type}"}

    training_processor = BoxDetectorProcessor(
        data_dir=config.DATA_DIR,
        model_path=config.BOX_DETECTOR_MODEL_PATH,
        test_ratio=config.BOX_DETECTOR_TEST_RATIO,
        epochs=training_epochs,
        augment_shift_regular=config.augment_shifts_regular,
        augment_shift_blueprint=config.augment_shifts_blueprint,
        augment_fill=config.EXTRACT_AUGMENT_FILL,
        augment_count=config.EXTRACT_AUGMENT_COUNT,
        test_blueprint_fraction=config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
        scale_regular=config.EXTRACT_REGULAR_SCALE,
        scale_blueprint=config.EXTRACT_BLUEPRINT_SCALE,
        preview_every_n_epochs=config.PREVIEW_EVERY_N_EPOCHS,
        initial_learning_rate=initial_learning_rate,
    )

    def progress_callback(epoch: int, total_epochs: int, metrics: Dict) -> None:
        update_task_progress(
            redis_client, task_id, evaluated=epoch, total_planned=total_epochs, partial_results=metrics
        )
        if (
            epoch > 0
            and config.PREVIEW_EVERY_N_EPOCHS > 0
            and epoch % config.PREVIEW_EVERY_N_EPOCHS == 0
        ):
            redis_client.setex(f"task:{task_id}:eval", 3600, json.dumps(metrics))

    def preview_callback(epoch: int, metrics: Dict, preview_payload: Dict) -> None:
        n_items = len(preview_payload.get("items", []))
        expected_ms = n_items * config.PREVIEW_MS_PER_IMAGE
        redis_client.setex(
            f"task:{task_id}:preview_expected_duration_ms", PREVIEW_TTL, str(expected_ms)
        )
        preview_json = json.dumps(preview_payload)
        redis_client.setex(f"task:{task_id}:latest_preview", PREVIEW_TTL, preview_json)
        redis_client.setex(LATEST_PREVIEW_KEY, PREVIEW_TTL, preview_json)
        redis_client.setex(f"task:{task_id}:last_preview_epoch", PREVIEW_TTL, str(epoch))
        logger.info("Preview generated at epoch %d (%d items)", epoch, n_items)

    def check_cancelled() -> bool:
        return redis_client.get(f"task:{task_id}:cancelled") == "1"

    def check_pending_evaluation() -> bool:
        return redis_client.llen(EVALUATION_QUEUE_NAME) > 0

    try:
        results = training_processor.process(
            task_id=task_id,
            progress_callback=progress_callback,
            preview_callback=preview_callback,
            check_cancelled=check_cancelled,
            resume_from_existing=resume_from_existing,
            resume_from_epoch=resume_from_epoch,
            check_pending_evaluation=check_pending_evaluation,
        )
        return results
    except TaskCancelledError:
        raise
    except Exception as e:
        return {"error": "training_failed", "message": str(e)}


def _finish_training_completed(
    redis_client: redis.Redis,
    config: Config,
    repo_root: Path,
    task_id: str,
    results: Dict[str, Any],
    model_type: str = "box_detector",
) -> None:
    """Write final preview (box_detector only) and completed status to Redis."""
    final_preview = results.get("final_preview")
    if final_preview and isinstance(final_preview, dict) and "items" in final_preview:
        preview_json = json.dumps(final_preview)
        redis_client.setex(f"task:{task_id}:latest_preview", PREVIEW_TTL, preview_json)
        redis_client.setex(LATEST_PREVIEW_KEY, PREVIEW_TTL, preview_json)
        logger.info(
            "Completion preview from processor (%d items), skipped eval_run_preview",
            len(final_preview.get("items", [])),
        )
    elif model_type == "box_detector":
        data_dir = repo_root / config.DATA_DIR
        logger.info("Running completion preview (data_dir=%s)", data_dir)
        t0 = time.perf_counter()
        preview_result = eval_run_preview(
            data_dir,
            config.BOX_DETECTOR_TEST_RATIO,
            config.augment_shifts_regular,
            config.augment_shifts_blueprint,
            config.EXTRACT_AUGMENT_FILL,
            config.EXTRACT_AUGMENT_COUNT,
            config.EXTRACT_REGULAR_SCALE,
            config.EXTRACT_BLUEPRINT_SCALE,
            config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if "error" not in preview_result:
            preview_payload = {
                "items": preview_result["items"],
                "scale_regular": preview_result["scale_regular"],
                "scale_blueprint": preview_result["scale_blueprint"],
            }
            preview_json = json.dumps(preview_payload)
            redis_client.setex(f"task:{task_id}:latest_preview", PREVIEW_TTL, preview_json)
            redis_client.setex(LATEST_PREVIEW_KEY, PREVIEW_TTL, preview_json)
            logger.info(
                "Completion preview generated in %d ms (%d items)",
                elapsed_ms,
                len(preview_result["items"]),
            )
        else:
            logger.warning(
                "Completion preview not written: %s",
                preview_result.get("message", preview_result.get("error", "unknown")),
            )
    results_for_status = {k: v for k, v in results.items() if k != "final_preview"}
    update_task_status(redis_client, task_id, "completed", results=results_for_status)


def run_training(redis_client: redis.Redis, config: Config, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run one training unit. Returns result dict to print to stdout."""
    task_id = task_data["task_id"]
    redis_client.hset(
        f"task:{task_id}:meta",
        mapping={"status": "processing", "task_type": "training"},
    )
    try:
        results = _run_training(redis_client, config, task_data)
    except TaskCancelledError:
        update_task_status(redis_client, task_id, "cancelled", error="Training cancelled")
        return {"cancelled": True}
    if results.get("suspended"):
        return results
    if "error" in results:
        update_task_status(
            redis_client,
            task_id,
            "failed",
            error=results.get("message", results.get("error", "Unknown error")),
        )
        return results
    repo_root = Path(__file__).resolve().parent.parent
    model_type = task_data.get("model_type", "box_detector")
    _finish_training_completed(redis_client, config, repo_root, task_id, results, model_type=model_type)
    return {k: v for k, v in results.items() if k != "final_preview"}


def run_evaluation(redis_client: redis.Redis, config: Config, task_data: Dict[str, Any]) -> int:
    """Run one evaluation task. Returns exit code 0 or 1."""
    task_id = task_data["task_id"]
    eval_type = task_data.get("type", "evaluate")
    logger.info("Processing evaluation task %s (type=%s)", task_id, eval_type)
    redis_client.hset(
        f"task:{task_id}:meta",
        mapping={"status": "processing", "task_type": "evaluation"},
    )
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = (repo_root / config.DATA_DIR).resolve()
    try:
        if eval_type == "evaluate":
            result = eval_run_evaluate(
                data_dir=data_dir,
                test_ratio=config.BOX_DETECTOR_TEST_RATIO,
                shift_regular=config.augment_shifts_regular,
                shift_blueprint=config.augment_shifts_blueprint,
                fill_mode=config.EXTRACT_AUGMENT_FILL,
                augment_count=config.EXTRACT_AUGMENT_COUNT,
                test_blueprint_fraction=config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
            )
        elif eval_type == "preview":
            result = eval_run_preview(
                data_dir=data_dir,
                test_ratio=config.BOX_DETECTOR_TEST_RATIO,
                shift_regular=config.augment_shifts_regular,
                shift_blueprint=config.augment_shifts_blueprint,
                fill_mode=config.EXTRACT_AUGMENT_FILL,
                augment_count=config.EXTRACT_AUGMENT_COUNT,
                scale_regular=config.EXTRACT_REGULAR_SCALE,
                scale_blueprint=config.EXTRACT_BLUEPRINT_SCALE,
                test_blueprint_fraction=config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
            )
        elif eval_type == "model_evaluation":
            model_id = task_data.get("model_id")
            scope = task_data.get("scope", "all")
            if scope not in ("all", "test"):
                scope = "all"
            result = eval_run_model_evaluation_combined(
                data_dir=data_dir,
                shift_regular=config.augment_shifts_regular,
                shift_blueprint=config.augment_shifts_blueprint,
                fill_mode=config.EXTRACT_AUGMENT_FILL,
                augment_count=config.EXTRACT_AUGMENT_COUNT,
                scale_regular=config.EXTRACT_REGULAR_SCALE,
                scale_blueprint=config.EXTRACT_BLUEPRINT_SCALE,
                test_ratio=config.BOX_DETECTOR_TEST_RATIO,
                test_blueprint_fraction=config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
                model_id=model_id,
                scope=scope,
            )
            if "error" in result:
                update_task_status(
                    redis_client,
                    task_id,
                    "failed",
                    error=result.get("message", result.get("error", "Unknown error")),
                )
                return 1
        else:
            update_task_status(
                redis_client, task_id, "failed", error=f"Unknown evaluation type: {eval_type}"
            )
            return 1

        if "error" in result:
            update_task_status(
                redis_client,
                task_id,
                "failed",
                error=result.get("message", result.get("error", "Unknown error")),
            )
            return 1

        model_format = result.pop("model_format", None)
        if model_format is not None:
            redis_client.setex(
                f"task:{task_id}:model_format", CURRENT_TASK_EXPIRY, model_format
            )
        update_task_status(redis_client, task_id, "completed", results=result)
        logger.info("Completed evaluation task %s", task_id)
        return 0
    except Exception as e:
        logger.exception("Failed to process evaluation task %s", task_id)
        update_task_status(redis_client, task_id, "failed", error=str(e))
        return 1


def _clear_current_task(redis_client: redis.Redis, current_key: str) -> None:
    try:
        redis_client.delete(current_key)
    except Exception as e:
        logger.warning("Failed to clear current task key: %s", e)


def run_recommendation(redis_client: redis.Redis, config: Config, task_data: Dict[str, Any]) -> int:
    """Run one recommendation task. Returns exit code 0 or 1."""
    task_id = task_data["task_id"]
    weights = json.loads(task_data["weights"])
    constraints = json.loads(task_data["constraints"])
    limit = int(task_data["limit"])
    logger.info("Processing task %s", task_id)
    redis_client.setex(CURRENT_TASK_KEY, CURRENT_TASK_EXPIRY, task_id)
    update_task_status(redis_client, task_id, "processing")

    def progress_callback(
        evaluated: int, total_planned: int, partial_results: Optional[Dict]
    ) -> None:
        update_task_progress(
            redis_client, task_id, evaluated=evaluated, total_planned=total_planned, partial_results=partial_results
        )

    def check_cancelled() -> bool:
        return redis_client.get(f"task:{task_id}:cancelled") == "1"

    processor = RecommendationProcessor(config.DATA_FILE_PATH)
    try:
        results = processor.process(
            weights=weights,
            constraints=constraints,
            limit=limit,
            progress_callback=progress_callback,
            check_cancelled=check_cancelled,
        )
        _clear_current_task(redis_client, CURRENT_TASK_KEY)
        update_task_status(redis_client, task_id, "completed", results=results)
        logger.info("Completed task %s", task_id)
        return 0
    except TaskCancelledError:
        _clear_current_task(redis_client, CURRENT_TASK_KEY)
        update_task_status(
            redis_client, task_id, "cancelled", error="Cancelled (a new task was started)"
        )
        logger.info("Task %s was cancelled", task_id)
        return 0
    except Exception as e:
        _clear_current_task(redis_client, CURRENT_TASK_KEY)
        logger.exception("Failed to process task %s", task_id)
        update_task_status(redis_client, task_id, "failed", error=str(e))
        return 1


def main() -> int:
    if len(sys.argv) != 3:
        logger.error("Usage: python -m task.run_task <training|evaluation|recommendation> '<json_payload>'")
        return 1
    task_type = sys.argv[1].lower().strip()
    try:
        task_data = json.loads(sys.argv[2])
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON payload: %s", e)
        return 1
    if task_type not in ("training", "evaluation", "recommendation"):
        logger.error("Unknown task type: %s", task_type)
        return 1

    config = Config()
    redis_client = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD,
        decode_responses=True,
    )

    if task_type == "training":
        result = run_training(redis_client, config, task_data)
        # Single JSON line to stdout for parent to parse
        print(json.dumps(result), flush=True)
        if result.get("suspended"):
            return 0
        if "error" in result or result.get("cancelled"):
            return 1
        return 0

    if task_type == "evaluation":
        return run_evaluation(redis_client, config, task_data)

    return run_recommendation(redis_client, config, task_data)


if __name__ == "__main__":
    sys.exit(main())
