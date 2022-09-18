import asyncio
from threading import Thread


def chunk(sequence, size):
    """Break `sequence` into chunks which are at most `size` long.

    Returns:
        None

    Yields:
        Chunks in the order they are being made.
    """

    s = sequence
    while len(s) != 0:
        yield s[:size]
        s = s[size:]


def split_at_index(sequence, index):
    """Split `sequence` into left and right part.

    Args:
        index: Place at which to make the split.

    Returns:
        Tuple with left and right part.
    """

    return sequence[:index], sequence[index:]


def create_thread_loop(name):
    """Create new thread and then start new asyncio event loop inside it.

    Args:
        name: Name of the new thread.

    Returns:
        Tuple containing asyncio loop and `kill` function which will stop the loop and the
        associated thread.
    """

    loop = asyncio.new_event_loop()
    kill_switch = loop.create_future()

    # this function will be called in newly created thread.
    def start_loop(loop_to_start):
        asyncio.set_event_loop(loop_to_start)
        loop_to_start.run_until_complete(kill_switch)

    t = Thread(target=start_loop, args=(loop,), name=name)
    t.start()

    def kill():
        loop.call_soon_threadsafe(lambda: kill_switch.set_result(True))

    return loop, kill


def create_task_callback(log):
    """Creates callback which will log when the task was cancelled. It is used when we schedule
    the task on the loop and want to know that it was cancelled.

    Args:
        log: logger which will be used to report task cancellation

    Returns:
        Callback
    """

    def callback(future):
        try:
            return future.result()
        except asyncio.CancelledError:
            log.debug("Task cancelled")

    return callback
