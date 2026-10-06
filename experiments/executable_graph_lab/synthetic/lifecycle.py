"""Run-owned resources. Cleanup is scheduled from declared users, not graph sinks."""
import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceUse:
    name: str
    scope: str  # recording or camera; distinct from dispatch capacity


class SyntheticHandle:
    def __init__(self):
        self.closed = False
        self.close_count = 0

    async def close(self):
        self.close_count += 1
        self.closed = True


class ResourceOwner:
    def __init__(self, plan, event, factory=None):
        self.event = event
        self.factory = factory or (lambda key: SyntheticHandle())
        self.users, self.branches, self.records, self.tasks = {}, {}, {}, set()
        nodes = {n.id: n for n in plan.nodes}
        for work in plan.work:
            for use in nodes[work.node].resource_uses:
                key = self.key(use, work)
                self.users.setdefault(key, set()).add(work.id)
                self.branches.setdefault(key, set()).add(nodes[work.node].branch)

    @staticmethod
    def key(use, work):
        return f'{use.name}/{work.camera if use.scope == "camera" else "all"}'

    def acquire(self, node, work):
        # Factory returns an owned shell synchronously; async initialization must
        # happen after registration so cancellation can always find and close it.
        for use in node.resource_uses:
            key = self.key(use, work)
            if key not in self.records:
                handle = self.factory(key)
                self.records[key] = dict(handle=handle, state='open', error=None)
                self.event('resource_opened', node.id, key)
            if self.records[key]['state'] != 'open':
                raise RuntimeError(f'Resource is no longer usable: {key}')

    async def close(self, key):
        record = self.records[key]
        try:
            await record['handle'].close()
            record['state'] = 'closed'
            self.event('resource_closed', detail=key)
        except Exception as error:
            record['state'], record['error'] = 'cleanup_failed', str(error)
            self.event('resource_cleanup_failed', detail=f'{key}: {error}')

    async def finish(self, node, work):
        for use in node.resource_uses:
            key = self.key(use, work)
            record = self.records[key]
            if record['state'] == 'open':
                await asyncio.shield(self.start_close(key))
            if record['state'] != 'closed':
                raise RuntimeError(f'Resource finalization failed: {key}')

    def start_close(self, key):
        self.records[key]['state'] = 'closing'
        task = asyncio.create_task(self.close(key))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def sweep(self, states, wakeup):
        for key, record in self.records.items():
            if record['state'] == 'open' and all(states[w] not in ('pending', 'running') for w in self.users[key]):
                task = self.start_close(key)
                task.add_done_callback(lambda _: wakeup.set())

    async def close_all(self):
        if self.tasks: await asyncio.gather(*tuple(self.tasks))
        for key, record in self.records.items():
            if record['state'] == 'open':
                record['state'] = 'closing'
                await self.close(key)

    def describe(self):
        return [dict(key=key, state=value['state'], error=value['error'], simulated=True)
                for key, value in self.records.items()]
