import threading
import O4_UI_Utils as UI

################################################################################
class parallel_worker(threading.Thread):
    def __init__(self, task, queue, progress=None, success=[1]):
        threading.Thread.__init__(self)
        self._task = task
        self._queue = queue
        self._progress = progress
        self._success = success

    def run(self):
        while True:
            args = self._queue.get()
            if isinstance(args, str) and args == "quit":
                try:
                    UI.progress_bar(self._progress["bar"], 100)
                except:
                    pass
                return 1
            try:
                result = self._task(*args)
                self._success[0] = result and self._success[0]
            except Exception as e:
                UI.vprint(0, f"ERROR in parallel worker: {e}")
                self._success[0] = 0
            if self._progress:
                self._progress["done"] += 1
                UI.progress_bar(
                    self._progress["bar"],
                    int(
                        100
                        * self._progress["done"]
                        / (self._progress["done"] + self._queue.qsize())
                    ),
                )
            if UI.red_flag:
                return 0

################################################################################
def parallel_execute(task, queue, nbr_workers, progress=None):
    workers = []
    success = [1]
    for _ in range(nbr_workers):
        queue.put("quit")
        worker = parallel_worker(task, queue, progress, success)
        worker.start()
        workers.append(worker)
    for worker in workers:
        worker.join()
    if UI.red_flag:
        return 0
    return success[0]


################################################################################
def parallel_launch(task, queue, nbr_workers, progress=None):
    workers = []
    success = [1]  # Shared success tracker
    for _ in range(nbr_workers):
        worker = parallel_worker(task, queue, progress, success)
        worker.start()
        workers.append(worker)
    return workers, success

################################################################################
def parallel_join(workers, success=None):
    for worker in workers:
        worker.join()
    if success is not None:
        return success[0]
    return 1