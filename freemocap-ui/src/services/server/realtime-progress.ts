import type {TaskRegistrySnapshot} from './transport/message-contract';

/** Select existing registry records; their result is the operation's full snapshot. */
export function latestRealtimeTask(tasks: TaskRegistrySnapshot['tasks'], type: 'realtime_startup' | 'onnx_preparation', pipelineId?: string | null) {
    return tasks.filter(task => task.task_type === type &&
        (type === 'realtime_startup' || task.result?.pipeline_id === pipelineId))
        .reduce<TaskRegistrySnapshot['tasks'][number] | null>((latest, task) =>
            !latest || Date.parse(task.created_at) >= Date.parse(latest.created_at) ? task : latest, null);
}
