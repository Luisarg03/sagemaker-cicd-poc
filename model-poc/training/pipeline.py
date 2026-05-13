''' Crear SageMaker Pipeline de entrenamiento (compatible con ministack y modo local). '''

import os
import json
import argparse
from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.processing import Processor, ProcessingInput, ProcessingOutput
from sagemaker.tuner import ContinuousParameter, HyperparameterTuner, IntegerParameter
from sagemaker.workflow.parameters import ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession, LocalPipelineSession
from sagemaker.workflow.steps import ProcessingStep, TuningStep
from sagemaker.workflow.functions import Join
from sagemaker.workflow.execution_variables import ExecutionVariables

# Global configurations (can be overridden by config.json)
CONFIG_DEFAULT = {
    "account_id": "058528764918",
    "region": "us-east-1",
    "name_model": "placeholder",
    "team": "placeholder",
    "cc": "9946100000",
    "s3_bucket": "interbank-datalake-dev-us-east-1-058528764918-mlartifacts",
    "s3_prefix": "model_pipelines/placeholder",
    "image_uri_processing": "058528764918.dkr.ecr.us-east-1.amazonaws.com/sagemaker-processing-uv:py3.13-cpu",
    "image_uri_training": "058528764918.dkr.ecr.us-east-1.amazonaws.com/sagemaker-training-uv:py3.13-cpu",
    "role_arn": "arn:aws:iam::058528764918:role/AmazonSageMaker-ExecutionRole"
}

def load_config(config_path: str):
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            user_config = json.load(f)
            config = CONFIG_DEFAULT.copy()
            config.update(user_config)
            # Dynamic prefix if not provided
            if 's3_prefix' not in user_config:
                config['s3_prefix'] = f"model_pipelines/{config['name_model']}"
            return config
    return CONFIG_DEFAULT

def build_preprocessing_step(
    session: PipelineSession,
    tags: list[dict],
    instance_type: ParameterString,
    config: dict
) -> ProcessingStep:
    s3_input_code = f's3://{config["s3_bucket"]}/{config["s3_prefix"]}/code/training/artifacts/preprocessing/sourcedir.tar.gz'
    s3_output_base = Join(
        on='/',
        values=[
            f's3://{config["s3_bucket"]}/{config["s3_prefix"]}/executions/training',
            ExecutionVariables.START_DATETIME,
            'preprocessing/outputs',
        ],
    )

    processor = Processor(
        image_uri=config["image_uri_processing"],
        role=config["role_arn"],
        instance_type=instance_type,
        instance_count=1,
        volume_size_in_gb=10,
        sagemaker_session=session,
        tags=tags,
    )

    inputs = [
        ProcessingInput(
            input_name='code',
            source=s3_input_code,
            destination='/opt/ml/processing/input/code',
        )
    ]

    outputs = [
        ProcessingOutput(
            output_name='dataset',
            source='/opt/ml/processing/output/dataset',
            destination=Join(on='/', values=[s3_output_base, 'dataset']),
        ),
        ProcessingOutput(
            output_name='pipeline',
            source='/opt/ml/processing/output/pipeline',
            destination=Join(on='/', values=[s3_output_base, 'pipeline']),
        ),
        ProcessingOutput(
            output_name='uv',
            source='/opt/ml/processing/output/uv',
            destination=Join(on='/', values=[s3_output_base, 'uv']),
        )
    ]

    step_args = processor.run(inputs=inputs, outputs=outputs)
    return ProcessingStep(name='Preprocessing', step_args=step_args)

def build_training_step(
    session: PipelineSession,
    tags: list[dict],
    preprocessing_step: ProcessingStep,
    instance_type: ParameterString,
    max_jobs: ParameterInteger,
    max_parallel_jobs: ParameterInteger,
    config: dict
) -> TuningStep:
    s3_input_code = f's3://{config["s3_bucket"]}/{config["s3_prefix"]}/code/training/artifacts/training/sourcedir.tar.gz'
    s3_output = Join(
        on='/',
        values=[
            f's3://{config["s3_bucket"]}/{config["s3_prefix"]}/executions/training',
            ExecutionVariables.START_DATETIME,
            'training/outputs',
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
    )

    estimator.set_hyperparameters(
        eval_metric='auc',
        early_stopping_rounds=20,
        tree_method='hist',
        random_state=123,
    )

    hyperparameter_ranges = {
        'learning_rate': ContinuousParameter(0.001, 0.1),
        'n_estimators': IntegerParameter(1000, 8000),
        'max_depth': IntegerParameter(3, 5),
        'min_child_weight': ContinuousParameter(1, 10),
        'subsample': ContinuousParameter(0.5, 1.0),
        'colsample_bytree': ContinuousParameter(0.5, 1.0),
        'reg_alpha': ContinuousParameter(0.0, 1.0),
        'reg_lambda': ContinuousParameter(0.0, 1.0),
    }

    tuner = HyperparameterTuner(
        estimator=estimator,
        hyperparameter_ranges=hyperparameter_ranges,
        metric_definitions=[{'Name': 'validation:auc', 'Regex': 'validation_1-auc:([0-9\\.]+)'}],
        objective_metric_name='validation:auc',
        objective_type='Maximize',
        max_jobs=max_jobs,
        max_parallel_jobs=max_parallel_jobs,
        strategy='Bayesian',
        random_seed=123,
        tags=tags,
    )

    s3_dataset = preprocessing_step.properties.ProcessingOutputConfig.Outputs['dataset'].S3Output.S3Uri
    inputs = {
        'code': TrainingInput(s3_data=s3_input_code),
        'train': TrainingInput(s3_data=Join(on='/', values=[s3_dataset, 'train.csv']), content_type='csv'),
        'val': TrainingInput(s3_data=Join(on='/', values=[s3_dataset, 'val.csv']), content_type='csv'),
    }

    step_args = tuner.fit(inputs=inputs)
    return TuningStep(name='Training', step_args=step_args)

def build_validation_step(
    session: PipelineSession,
    tags: list[dict],
    preprocessing_step: ProcessingStep,
    training_step: TuningStep,
    instance_type: ParameterString,
    config: dict
) -> ProcessingStep:
    s3_input_code = f's3://{config["s3_bucket"]}/{config["s3_prefix"]}/code/training/artifacts/validation/sourcedir.tar.gz'
    s3_output_base = Join(
        on='/',
        values=[
            f's3://{config["s3_bucket"]}/{config["s3_prefix"]}/executions/training',
            ExecutionVariables.START_DATETIME,
            'validation/outputs',
        ],
    )

    s3_dataset = preprocessing_step.properties.ProcessingOutputConfig.Outputs['dataset'].S3Output.S3Uri
    s3_input_model = training_step.get_top_model_s3_uri(
        top_k=0,
        s3_bucket=config["s3_bucket"],
        prefix=f'{config["s3_prefix"]}/executions/training',
    )

    processor = Processor(
        image_uri=config["image_uri_processing"],
        role=config["role_arn"],
        instance_type=instance_type,
        instance_count=1,
        volume_size_in_gb=10,
        sagemaker_session=session,
        tags=tags,
    )

    inputs = [
        ProcessingInput(input_name='code', source=s3_input_code, destination='/opt/ml/processing/input/code'),
        ProcessingInput(input_name='dataset', source=s3_dataset, destination='/opt/ml/processing/input/dataset'),
        ProcessingInput(input_name='model', source=s3_input_model, destination='/opt/ml/processing/input/model')
    ]

    outputs = [
        ProcessingOutput(output_name='reports', source='/opt/ml/processing/output/reports', destination=Join(on='/', values=[s3_output_base, 'reports'])),
        ProcessingOutput(output_name='uv', source='/opt/ml/processing/output/uv', destination=Join(on='/', values=[s3_output_base, 'uv']))
    ]

    step_args = processor.run(inputs=inputs, outputs=outputs)
    return ProcessingStep(name='Validation', step_args=step_args)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true', help='Use LocalPipelineSession')
    parser.add_argument('--s3-endpoint-url', help='S3 endpoint URL for Local/Ministack')
    parser.add_argument('--config', default='model-poc/config.json', help='Path to config.json')
    parser.add_argument('--upsert-only', action='store_true', help='Do not start pipeline execution')
    args = parser.parse_args()

    config = load_config(args.config)

    if args.s3_endpoint_url:
        # Inyectar el endpoint de S3 en la session de sagemaker si es necesario
        # Para ministack, sagemaker local session necesita saber donde esta S3
        os.environ['AWS_ENDPOINT_URL_S3'] = args.s3_endpoint_url

    if args.local:
        session = LocalPipelineSession(default_bucket=config['s3_bucket'])
    else:
        session = PipelineSession(default_bucket=config['s3_bucket'])

    tags = [
        {'Key': 'I_RESPONSABLE_LT', 'Value': config['name_model']},
        {'Key': 'I_CUENTA', 'Value': config['account_id']},
        {'Key': 'I_TEAM', 'Value': config['team']},
        {'Key': 'I_CC', 'Value': config['cc']},
    ]

    # Parameters
    preprocessing_instance_type = ParameterString(name='PreprocessingInstanceType', default_value='ml.m5.xlarge')
    training_instance_type = ParameterString(name='TrainingInstanceType', default_value='ml.m5.xlarge')
    training_max_jobs = ParameterInteger(name='TrainingMaxJobs', default_value=2)
    training_max_parallel_jobs = ParameterInteger(name='TrainingMaxParallelJobs', default_value=1)
    validation_instance_type = ParameterString(name='ValidationInstanceType', default_value='ml.m5.xlarge')

    # Build Steps
    prep_step = build_preprocessing_step(session, tags, preprocessing_instance_type, config)
    train_step = build_training_step(session, tags, prep_step, training_instance_type, training_max_jobs, training_max_parallel_jobs, config)
    val_step = build_validation_step(session, tags, prep_step, train_step, validation_instance_type, config)

    pipeline = Pipeline(
        name=f"{config['name_model']}-training-pipeline",
        parameters=[preprocessing_instance_type, training_instance_type, training_max_jobs, training_max_parallel_jobs, validation_instance_type],
        steps=[prep_step, train_step, val_step],
        sagemaker_session=session,
    )

    pipeline.upsert(role_arn=config['role_arn'], tags=tags)

    if not args.upsert_only:
        execution = pipeline.start()
        if not args.local:
            execution.wait()

if __name__ == '__main__':
    main()
