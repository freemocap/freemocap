import type {TaskRegistrySnapshot} from './transport/message-contract';

/** Select existing registry records; their result is the operation's full snapshot. */
export function latestRealtimeTask(tasks: TaskRegistrySnapshot['tasks']) {
    return tasks.filter(task => task.task_type === 'realtime_startup')
        .reduce<TaskRegistrySnapshot['tasks'][number] | null>((latest, task) =>
            !latest || Date.parse(task.created_at) >= Date.parse(latest.created_at) ? task : latest, null);
}
