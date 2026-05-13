import argparse
import json
import os

from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.processing import ProcessingInput, ProcessingOutput, Processor
from sagemaker.workflow.execution_variables import ExecutionVariables
from sagemaker.workflow.functions import Join
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import LocalPipelineSession, PipelineSession
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

CONFIG_DEFAULT = {
    "account_id": "000000000000",
    "region": "us-east-1",
    "name_model": "placeholder",
    "team": "placeholder",
    "cc": "0000000000",
    "s3_bucket": "placeholder-bucket",
    "s3_prefix": "model_pipelines/placeholder",
    "image_uri_preprocessing": "000000000000.dkr.ecr.us-east-1.amazonaws.com/placeholder:preprocessing",
    "image_uri_training": "000000000000.dkr.ecr.us-east-1.amazonaws.com/placeholder:training",
    "image_uri_validation": "000000000000.dkr.ecr.us-east-1.amazonaws.com/placeholder:validation",
    "role_arn": "arn:aws:iam::000000000000:role/SageMakerExecutionRole",
}


def load_config(config_path: str) -> dict:
    if os.path.exists(config_path):
        with open(config_path) as f:
            user_config = json.load(f)
            config = CONFIG_DEFAULT.copy()
            config.update(user_config)
            if "s3_prefix" not in user_config:
                config["s3_prefix"] = f"model_pipelines/{config['name_model']}"
            return config
    return CONFIG_DEFAULT


def build_preprocessing_step(
    session: PipelineSession,
    tags: list[dict],
    instance_type: ParameterString,
    config: dict,
) -> ProcessingStep:
    s3_input_code = f"s3://{config['s3_bucket']}/{config['s3_prefix']}/{config['name_model']}/code/training/artifacts/preprocessing/sourcedir.tar.gz"
    s3_output_base = Join(
        on="/",
        values=[
            f"s3://{config['s3_bucket']}/{config['s3_prefix']}/executions/training",
            ExecutionVariables.START_DATETIME,
            "preprocessing/outputs",
        ],
    )

    processor = Processor(
        image_uri=config["image_uri_preprocessing"],
        role=config["role_arn"],
        instance_type=instance_type,
        instance_count=1,
        volume_size_in_gb=10,
        sagemaker_session=session,
        tags=tags,
    )

    inputs = [
        ProcessingInput(
            input_name="code",
            source=s3_input_code,
            destination="/opt/ml/processing/input/code",
        )
    ]

    outputs = [
        ProcessingOutput(
            output_name="dataset",
            source="/opt/ml/processing/output/dataset",
            destination=Join(on="/", values=[s3_output_base, "dataset"]),
        ),
        ProcessingOutput(
            output_name="pipeline",
            source="/opt/ml/processing/output/pipeline",
            destination=Join(on="/", values=[s3_output_base, "pipeline"]),
        ),
        ProcessingOutput(
            output_name="uv",
            source="/opt/ml/processing/output/uv",
            destination=Join(on="/", values=[s3_output_base, "uv"]),
        ),
    ]

    step_args = processor.run(inputs=inputs, outputs=outputs)
    return ProcessingStep(name="Preprocessing", step_args=step_args)


def build_training_step(
    session: PipelineSession,
    tags: list[dict],
    preprocessing_step: ProcessingStep,
    instance_type: ParameterString,
    config: dict,
) -> TrainingStep:
    s3_input_code = f"s3://{config['s3_bucket']}/{config['s3_prefix']}/{config['name_model']}/code/training/artifacts/training/sourcedir.tar.gz"
    s3_output = Join(
        on="/",
        values=[
            f"s3://{config['s3_bucket']}/{config['s3_prefix']}/executions/training",
            ExecutionVariables.START_DATETIME,
            "training/outputs",
        ],
    )

    estimator = Estimator(
        image_uri=config["image_uri_training"],
        role=config["role_arn"],
        instance_type=instance_type,
        instance_count=1,
        volume_size=10,
        output_path=s3_output,
        sagemaker_session=session,
        tags=tags,
        hyperparameters={
            "eval_metric": "auc",
            "early_stopping_rounds": 20,
            "tree_method": "hist",
            "random_state": 123,
        },
    )

    s3_dataset = preprocessing_step.properties.ProcessingOutputConfig.Outputs[
        "dataset"
    ].S3Output.S3Uri
    inputs = {
        "code": TrainingInput(s3_data=s3_input_code),
        "train": TrainingInput(
            s3_data=Join(on="/", values=[s3_dataset, "train.csv"]), content_type="csv"
        ),
    }

    step_args = estimator.fit(inputs=inputs)
    return TrainingStep(name="Training", step_args=step_args)


def build_validation_step(
    session: PipelineSession,
    tags: list[dict],
    preprocessing_step: ProcessingStep,
    training_step: TrainingStep,
    instance_type: ParameterString,
    config: dict,
) -> ProcessingStep:
    s3_input_code = f"s3://{config['s3_bucket']}/{config['s3_prefix']}/{config['name_model']}/code/training/artifacts/validation/sourcedir.tar.gz"
    s3_output_base = Join(
        on="/",
        values=[
            f"s3://{config['s3_bucket']}/{config['s3_prefix']}/executions/training",
            ExecutionVariables.START_DATETIME,
            "validation/outputs",
        ],
    )

    s3_dataset = preprocessing_step.properties.ProcessingOutputConfig.Outputs[
        "dataset"
    ].S3Output.S3Uri
    s3_input_model = training_step.properties.ModelArtifacts.S3ModelArtifacts

    processor = Processor(
        image_uri=config["image_uri_validation"],
        role=config["role_arn"],
        instance_type=instance_type,
        instance_count=1,
        volume_size_in_gb=10,
        sagemaker_session=session,
        tags=tags,
    )

    inputs = [
        ProcessingInput(
            input_name="code",
            source=s3_input_code,
            destination="/opt/ml/processing/input/code",
        ),
        ProcessingInput(
            input_name="dataset",
            source=s3_dataset,
            destination="/opt/ml/processing/input/dataset",
        ),
        ProcessingInput(
            input_name="model",
            source=s3_input_model,
            destination="/opt/ml/processing/input/model",
        ),
    ]

    outputs = [
        ProcessingOutput(
            output_name="reports",
            source="/opt/ml/processing/output/reports",
            destination=Join(on="/", values=[s3_output_base, "reports"]),
        ),
        ProcessingOutput(
            output_name="uv",
            source="/opt/ml/processing/output/uv",
            destination=Join(on="/", values=[s3_output_base, "uv"]),
        ),
    ]

    step_args = processor.run(inputs=inputs, outputs=outputs)
    return ProcessingStep(name="Validation", step_args=step_args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--s3-endpoint-url")
    parser.add_argument("--config", default="model-2/config.json")
    parser.add_argument("--upsert-only", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.s3_endpoint_url:
        os.environ["AWS_ENDPOINT_URL_S3"] = args.s3_endpoint_url

    if args.local:
        session = LocalPipelineSession(default_bucket=config["s3_bucket"])
    else:
        session = PipelineSession(default_bucket=config["s3_bucket"])

    tags = [
        {"Key": "I_RESPONSABLE_LT", "Value": config["name_model"]},
        {"Key": "I_CUENTA", "Value": config["account_id"]},
        {"Key": "I_TEAM", "Value": config["team"]},
        {"Key": "I_CC", "Value": config["cc"]},
    ]

    preprocessing_instance_type = ParameterString(
        name="PreprocessingInstanceType", default_value="ml.m5.xlarge"
    )
    training_instance_type = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.xlarge"
    )
    validation_instance_type = ParameterString(
        name="ValidationInstanceType", default_value="ml.m5.xlarge"
    )

    prep_step = build_preprocessing_step(
        session, tags, preprocessing_instance_type, config
    )
    train_step = build_training_step(
        session, tags, prep_step, training_instance_type, config
    )
    val_step = build_validation_step(
        session, tags, prep_step, train_step, validation_instance_type, config
    )

    pipeline = Pipeline(
        name=f"{config['name_model']}-training-pipeline",
        parameters=[
            preprocessing_instance_type,
            training_instance_type,
            validation_instance_type,
        ],
        steps=[prep_step, train_step, val_step],
        sagemaker_session=session,
    )

    pipeline.upsert(role_arn=config["role_arn"], tags=tags)

    if not args.upsert_only:
        execution = pipeline.start()
        if not args.local:
            execution.wait()


if __name__ == "__main__":
    main()
