import asyncio

import pytest

from freemocap_stream import Latest, StreamConnection


async def settle() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


async def stop(*tasks: asyncio.Task) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def test_a_slow_client_receives_fewer_newer_frames():
    async def scenario():
        frames = Latest()
        fast, slow, release = [], [], asyncio.Event()

        async def send_fast(message):
            fast.append(message)

        async def send_slow(message):
            slow.append(message)
            await release.wait()

        followers = [asyncio.create_task(StreamConnection(send).follow(frames)) for send in (send_fast, send_slow)]
        for number in range(20):
            frames.publish(b"frame %d" % number)
            await settle()
        release.set()
        await settle()
        await stop(*followers)
        return fast, slow

    fast, slow = asyncio.run(scenario())
    assert fast == [b"frame %d" % number for number in range(20)]
    assert slow == [b"frame 0", b"frame 19"]


def test_sends_never_overlap_on_one_connection():
    async def scenario():
        frames, state = Latest(), Latest()
        active, most_active, sent = 0, 0, []

        async def send(message):
            nonlocal active, most_active
            active += 1
            most_active = max(most_active, active)
            await asyncio.sleep(0)
            sent.append(message)
            active -= 1

        connection = StreamConnection(send, send)
        follower = asyncio.create_task(connection.follow(frames, state))
        for number in range(30):
            frames.publish(b"frame %d" % number)
            state.publish(b"state %d" % number)
            pings = [asyncio.create_task(connection.receive_text("ping")) for _ in range(2)]
            await settle()
            await asyncio.gather(*pings)
        await stop(follower)
        return most_active, sent

    most_active, sent = asyncio.run(scenario())
    assert most_active == 1
    assert b"frame 29" in sent and b"state 29" in sent and sent.count("pong") == 60


def test_ping_gets_pong_and_other_text_goes_to_the_application():
    async def scenario():
        texts = []

        async def send_text(text):
            texts.append(text)

        async def send_bytes(_message):
            pass

        connection = StreamConnection(send_bytes, send_text)
        results = [await connection.receive_text(text) for text in ("ping", "pong", '{"frameNumber": 3}')]
        return texts, results

    texts, results = asyncio.run(scenario())
    assert texts == ["pong"]
    assert results == [None, None, '{"frameNumber": 3}']


def test_a_late_joiner_gets_the_current_message_at_once():
    async def scenario():
        state, sent = Latest(), []
        state.publish(b"state 1")
        state.publish(b"state 2")

        async def send(message):
            sent.append(message)

        follower = asyncio.create_task(StreamConnection(send).follow(state))
        await settle()
        await stop(follower)
        return sent

    assert asyncio.run(scenario()) == [b"state 2"]


def test_one_client_leaving_does_not_disturb_the_others():
    async def scenario():
        frames, staying = Latest(), []

        async def keep(message):
            staying.append(message)

        async def ignore(_message):
            pass

        stayer = asyncio.create_task(StreamConnection(keep).follow(frames))
        leaver = asyncio.create_task(StreamConnection(ignore).follow(frames))
        await settle()
        await stop(leaver)
        frames.publish(b"frame 1")
        await settle()
        await stop(stayer)
        return staying

    assert asyncio.run(scenario()) == [b"frame 1"]


def test_a_failed_send_ends_following_and_is_raised():
    async def scenario():
        frames, state = Latest(), Latest()

        async def broken(_message):
            raise ConnectionResetError("client went away")

        follower = asyncio.create_task(StreamConnection(broken).follow(frames, state))
        frames.publish(b"frame 1")
        with pytest.raises(ConnectionResetError):
            await follower
        state.publish(b"state 1")
        await settle()
        return [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    assert asyncio.run(scenario()) == []
